"""Browser-session credentials. Keys stay in process memory and out of map data."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from dotenv import dotenv_values

from server.ai.types import AIError

ROOT = Path(__file__).resolve().parents[1]
COOKIE_NAME = "failure_session"


@dataclass
class ClientSession:
    keys: dict[str, str] = field(default_factory=dict, repr=False)
    selected_provider: str | None = None


CLIENTS: dict[str, ClientSession] = {}


def browser_session(cookie: str | None) -> str:
    if cookie not in CLIENTS:
        cookie = uuid4().hex
        CLIENTS[cookie] = ClientSession()
    return cookie


def remember_key(owner: str, provider: str, key: str) -> None:
    if provider not in {"gemini", "groq"}:
        raise AIError("invalid_request", "Choose Gemini or Groq for the AI key.", status=422)
    if not isinstance(key, str) or not key.strip() or len(key) > 4096:
        raise AIError("invalid_key", "Enter a valid AI key.", status=401)
    CLIENTS[owner].keys[provider] = key.strip()
    CLIENTS[owner].selected_provider = provider


def available_keys(owner: str) -> dict[str, str]:
    values = dotenv_values(ROOT / ".env")
    keys = {
        provider: os.environ.get(f"{provider.upper()}_API_KEY")
        or values.get(f"{provider.upper()}_API_KEY")
        or ""
        for provider in ("gemini", "groq")
    }
    keys.update(CLIENTS[owner].keys)
    return keys


def safe_message(owner: str, message: str) -> str:
    # Provider failures are normally generic. Redact even if an unexpected SDK
    # message includes a credential; never include provider exception objects.
    for key in available_keys(owner).values():
        if key:
            message = message.replace(key, "[key hidden]")
    return message


def public_attempts(attempts: list[dict]) -> list[dict]:
    return [
        {key: row[key] for key in ("provider", "status", "error") if key in row} for row in attempts
    ]
