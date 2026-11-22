from dataclasses import replace

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import seed
from app.jobs import run_housekeeping
from app.main import create_app
from app.models import Agent, Holiday, Ticket
from conftest import PASSWORD


def test_seed_creates_nine_agents_holidays_and_demo_tickets_once(factory, settings):
    seed.seed_if_empty(factory, settings)
    seed.seed_if_empty(factory, settings)  # second call must be a no-op
    with factory() as s:
        agents = s.scalars(select(Agent)).all()
        assert len(agents) == 9
        assert [a.name for a in agents if a.role == "lead"] == ["Meera Nair"]
        assert s.scalar(select(func.count(Holiday.day))) == 12
        assert s.scalar(select(func.count(Ticket.id))) == 5


def test_demo_data_shows_late_waiting_and_reopenable_tickets(factory, settings, engine):
    app = create_app(replace(settings, seed_demo=True))  # start-up seeds the demo data
    with TestClient(app) as client:
        run_housekeeping(factory)
        r = client.post("/api/auth/login", json={"email": "meera@arvosystems.example", "password": PASSWORD})
        assert r.status_code == 200
        h = {"Authorization": f"Bearer {r.json()['token']}"}
        items = client.get("/api/tickets?view=active", headers=h).json()["items"]
        by_subject = {i["subject"]: i for i in items}
        assert by_subject["Entire finance team locked out of the portal"]["late"] is True
        assert by_subject["Dashboard totals look wrong"]["late"] is True
        assert by_subject["Export fails for large reports"]["sla"]["waiting_on_customer"] is True
        assert by_subject["Export fails for large reports"]["late"] is False
        assert by_subject["Invoices are not downloading"]["late"] is False
        resolved = client.get("/api/tickets?view=resolved", headers=h).json()["items"]
        assert [i["subject"] for i in resolved] == ["How do I add a new user?"]
        detail = client.get(f"/api/tickets/{resolved[0]['id']}", headers=h).json()
        assert detail["actions"]["can_reopen"] is True
        assert client.get("/api/audit/verify", headers=h).json()["intact"] is True
