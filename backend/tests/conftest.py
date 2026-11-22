"""Test fixtures.  The tests run against a real PostgreSQL (an embedded one started
by `pgserver`, or the server named by TEST_DATABASE_URL) because the integrity
guarantees we test live in database triggers and row locks."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

os.environ.setdefault("PASSWORD_ITERATIONS", "1000")

from app import clock, security  # noqa: E402
from app.config import Settings, normalize_database_url  # noqa: E402
from app.db import init_db, make_engine, make_session_factory  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Agent, Holiday  # noqa: E402

PASSWORD = "Passw0rd!test"


@pytest.fixture(scope="session")
def database_url():
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        yield normalize_database_url(explicit)
        return
    import pgserver

    # PGTEST_DIR lets you keep the data outside a synced folder (OneDrive and friends
    # delete the empty directories PostgreSQL needs).
    data_dir = Path(os.environ.get("PGTEST_DIR") or Path(__file__).resolve().parents[1] / ".pgtest")
    server = pgserver.get_server(data_dir, cleanup_mode="stop")
    yield normalize_database_url(server.get_uri())
    server.cleanup()


@pytest.fixture()
def settings(database_url):
    return Settings(
        database_url=database_url,
        secret_key="test-secret-test-secret-test-secret",
        environment="test",
        token_hours=24 * 365,  # tests jump the clock by weeks
        password_iterations=1000,
        static_dir=None,
        seed_demo=False,
        run_scheduler=False,
        demo_password=PASSWORD,
    )


@pytest.fixture()
def engine(settings):
    engine = make_engine(settings.database_url)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    init_db(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def factory(engine):
    return make_session_factory(engine)


@pytest.fixture()
def agents(factory):
    """Three agents and one lead, returned as {handle: id}."""
    ids = {}
    with factory() as session:
        for handle, role in (("asha", "agent"), ("ben", "agent"), ("chitra", "agent"), ("meera", "lead")):
            agent = Agent(
                name=handle.title(),
                email=f"{handle}@arvo.test",
                password_hash=security.hash_password(PASSWORD, 1000),
                role=role,
            )
            session.add(agent)
            session.flush()
            ids[handle] = agent.id
        session.commit()
    return ids


@pytest.fixture()
def holidays(factory):
    def add(*days):
        with factory() as session:
            for d in days:
                session.add(Holiday(day=d, name="Test holiday"))
            session.commit()

    return add


@pytest.fixture()
def client(settings, engine, agents):
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def login(client: TestClient, handle: str) -> dict:
    r = client.post("/api/auth/login", json={"email": f"{handle}@arvo.test", "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture()
def auth(client):
    cache: dict[str, dict] = {}

    def get(handle: str) -> dict:
        if handle not in cache:
            cache[handle] = login(client, handle)
        return cache[handle]

    return get


class FakeClock:
    """Lets a test say what time it is (default: a Monday morning, IST)."""

    def __init__(self, start: datetime):
        self.value = start

    def __call__(self) -> datetime:
        return self.value

    def set(self, value: datetime) -> None:
        self.value = value

    def advance(self, **kwargs) -> None:
        self.value += timedelta(**kwargs)


IST = timezone(timedelta(hours=5, minutes=30))


def ist(y, m, d, hh=0, mm=0) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=IST)


@pytest.fixture()
def fake_clock():
    fc = FakeClock(ist(2026, 11, 23, 10, 0))  # Monday 10:00 IST
    with clock.use_clock(fc):
        yield fc


def new_ticket(client, headers, **overrides):
    payload = {
        "subject": "Printer on fire",
        "description": "It is literally on fire.",
        "priority": "medium",
        "customer_name": "Cora Customer",
        "customer_email": "cora@customer.test",
    }
    payload.update(overrides)
    r = client.post("/api/tickets", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()
