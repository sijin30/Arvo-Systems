"""FastAPI dependencies: database session and the logged-in agent."""
from __future__ import annotations

from typing import Iterator

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import security
from .config import Settings
from .errors import DomainError, forbidden
from .models import Agent

_bearer = HTTPBearer(auto_error=False)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def current_agent(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Agent:
    if credentials is None:
        raise DomainError(401, "not_authenticated", "Please log in.")
    agent_id = security.read_token(settings, credentials.credentials)
    agent = session.get(Agent, agent_id) if agent_id is not None else None
    if agent is None or not agent.is_active:
        raise DomainError(401, "invalid_token", "Your session has expired. Please log in again.")
    return agent


def lead_agent(agent: Agent = Depends(current_agent)) -> Agent:
    if agent.role != "lead":
        raise forbidden("Only a lead can do this.", "lead_only")
    return agent
