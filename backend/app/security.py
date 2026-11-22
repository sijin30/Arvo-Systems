"""Password hashing and login tokens (standard library + PyJWT)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import timedelta

import jwt

from . import clock
from .config import Settings

_ALGORITHM = "HS256"


def hash_password(password: str, iterations: int) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.b64encode(salt).decode(),
        base64.b64encode(digest).decode(),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt_b64, digest_b64 = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def create_token(settings: Settings, agent_id: int) -> str:
    issued = clock.now()
    payload = {
        "sub": str(agent_id),
        "iat": int(issued.timestamp()),
        "exp": int((issued + timedelta(hours=settings.token_hours)).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)


def read_token(settings: Settings, token: str) -> int | None:
    try:
        # Expiry is checked against the application clock (below), not the library's.
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[_ALGORITHM],
            options={"verify_exp": False, "verify_iat": False},
        )
        if int(payload["exp"]) <= clock.now().timestamp():
            return None
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
