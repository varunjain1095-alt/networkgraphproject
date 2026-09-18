"""Load and query domain_config.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from config.env import project_root

CONFIG_FILE = project_root() / "domain_config.yaml"


def load_domain_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or CONFIG_FILE
    if not config_path.is_file():
        raise FileNotFoundError(f"Domain config not found: {config_path}")

    with config_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict):
        raise ValueError("domain_config.yaml must be a mapping at the top level")

    default_domain = data.get("default_domain")
    domains = data.get("domains")
    if not default_domain or not isinstance(domains, dict):
        raise ValueError("domain_config.yaml requires default_domain and domains")

    if default_domain not in domains:
        raise ValueError(f"default_domain '{default_domain}' not found in domains")

    return data


def get_active_domain(config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or load_domain_config()
    name = cfg["default_domain"]
    return cfg["domains"][name]


def entity_label(entity_key: str, config: dict[str, Any] | None = None) -> str:
    domain = get_active_domain(config)
    entities = domain.get("entities", {})
    if entity_key not in entities:
        raise KeyError(f"Unknown entity key: {entity_key}")
    return entities[entity_key]
