"""Runtime settings, read from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def normalize_database_url(url: str) -> str:
    """Accept the URL styles hosting providers hand out and force the psycopg3 driver."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    environment: str
    token_hours: int
    password_iterations: int
    static_dir: str | None
    seed_demo: bool
    run_scheduler: bool
    demo_password: str

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


def load_settings() -> Settings:
    environment = os.environ.get("APP_ENV", "development").lower()
    secret = os.environ.get("SECRET_KEY", "")
    if not secret:
        if environment == "production":
            raise RuntimeError("SECRET_KEY must be set when APP_ENV=production")
        secret = "dev-only-secret-change-me-dev-only-secret"
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set, e.g. postgresql://user:password@localhost:5432/frontdesk"
        )
    return Settings(
        database_url=normalize_database_url(database_url),
        secret_key=secret,
        environment=environment,
        token_hours=int(os.environ.get("TOKEN_HOURS", "12")),
        password_iterations=int(os.environ.get("PASSWORD_ITERATIONS", "200000")),
        static_dir=os.environ.get("STATIC_DIR") or None,
        seed_demo=_bool("SEED_DEMO", True),
        run_scheduler=_bool("RUN_SCHEDULER", True),
        demo_password=os.environ.get("DEMO_PASSWORD", "Frontdesk@123"),
    )
