"""Application factory."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from . import seed
from .config import Settings, load_settings
from .db import init_db, make_engine, make_session_factory
from .errors import DomainError
from .jobs import Scheduler
from .routes import api

log = logging.getLogger("frontdesk")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    engine = make_engine(settings.database_url)
    factory = make_session_factory(engine)
    scheduler = Scheduler(factory)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(engine)
        if settings.seed_demo:
            seed.seed_if_empty(factory, settings)
            seed.ensure_demo_customer(factory, settings)
        if settings.run_scheduler:
            scheduler.start()
        try:
            yield
        finally:
            scheduler.stop()
            engine.dispose()

    app = FastAPI(title="Frontdesk", version="1.0.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = factory

    @app.exception_handler(DomainError)
    async def domain_error(_: Request, exc: DomainError):
        return JSONResponse(exc.body(), status_code=exc.status_code)

    @app.exception_handler(IntegrityError)
    async def integrity_error(_: Request, exc: IntegrityError):
        log.warning("integrity error: %s", exc.orig)
        return JSONResponse(
            {"error": {"code": "conflict", "message": "That change conflicts with the current data."}},
            status_code=409,
        )

    app.include_router(api)
    _serve_frontend(app, settings)
    return app


def _serve_frontend(app: FastAPI, settings: Settings) -> None:
    static_dir = settings.static_dir
    if not static_dir or not os.path.isfile(os.path.join(static_dir, "index.html")):
        return
    root = os.path.realpath(static_dir)
    assets = os.path.join(root, "assets")
    if os.path.isdir(assets):
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        if path == "api" or path.startswith("api/"):
            return JSONResponse({"error": {"code": "not_found", "message": "Not found"}}, status_code=404)
        candidate = os.path.realpath(os.path.join(root, path))
        if path and candidate.startswith(root + os.sep) and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(root, "index.html"), headers={"Cache-Control": "no-cache"})
