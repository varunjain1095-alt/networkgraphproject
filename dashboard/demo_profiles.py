"""Display-only demo profile lookup for hover cards (not stored in the DB)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_PROFILES_PATH = Path(__file__).with_name("demo_profiles.json")
PROFILE_FIELDS = ("name", "gender", "location", "joined_on")


@dataclass(frozen=True)
class DemoProfile:
    user_id: str
    name: str
    gender: str
    location: str
    joined_on: str

    def as_rows(self) -> list[tuple[str, str]]:
        return [
            ("Name", self.name),
            ("Gender", self.gender),
            ("Location", self.location),
            ("Joined", self.joined_on),
        ]


def _profiles_path() -> Path:
    import os

    override = os.environ.get("DEMO_PROFILES_PATH", "").strip()
    if override:
        return Path(override)
    return DEFAULT_PROFILES_PATH


@lru_cache(maxsize=1)
def load_demo_profiles() -> dict[str, DemoProfile]:
    """Load demo profile mapping from JSON. Cached until process restart."""
    path = _profiles_path()
    if not path.is_file():
        return {}

    raw = json.loads(path.read_text(encoding="utf-8"))
    profiles: dict[str, DemoProfile] = {}
    for user_id, payload in raw.items():
        if user_id.startswith("_") or not isinstance(payload, dict):
            continue
        profiles[str(user_id)] = DemoProfile(
            user_id=str(user_id),
            name=str(payload.get("name", user_id)),
            gender=str(payload.get("gender", "—")),
            location=str(payload.get("location", "—")),
            joined_on=str(payload.get("joined_on", "—")),
        )
    return profiles


def get_demo_profile(user_id: str) -> DemoProfile | None:
    if not user_id:
        return None
    return load_demo_profiles().get(str(user_id))


def reload_demo_profiles() -> None:
    """Clear cached profiles (useful in tests)."""
    load_demo_profiles.cache_clear()
