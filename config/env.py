"""Load environment variables from .env at project root."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"


def load_env() -> None:
    """Load .env if present; safe to call multiple times."""
    load_dotenv(ENV_FILE, override=False)


def project_root() -> Path:
    """Resolved project root — works from any working directory."""
    load_env()
    explicit = os.getenv("PROJECT_ROOT")
    if explicit:
        return Path(explicit).expanduser().resolve()
    return PROJECT_ROOT


def get(key: str, default: str | None = None) -> str | None:
    load_env()
    return os.getenv(key, default)


def require(key: str) -> str:
    value = get(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


def resolve_path(key: str, default: str) -> Path:
    """Resolve env path relative to project root when not absolute."""
    raw = require(key) if get(key) else default
    path = Path(raw)
    if not path.is_absolute():
        path = project_root() / path
    return path.resolve()
