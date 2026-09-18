"""Generate core entity tables: organizations, users, items, trusted_sources."""

from __future__ import annotations

import json
import sqlite3

from datetime import timedelta

from generator.context import GenerationContext
from generator.time_utils import (
    ACTIVE_THRESHOLD_DAYS,
    growth_curve_join_date,
    random_date_after,
    simulation_end,
    to_iso,
)
from generator.time_utils import SIMULATION_START


def generate_core_entities(conn: sqlite3.Connection, ctx: GenerationContext) -> None:
    _generate_organizations(conn, ctx)
    _generate_users(conn, ctx)
    _generate_items(conn, ctx)
    _generate_sources(conn, ctx)
    ctx.stats["organizations"] = len(ctx.org_ids)
    ctx.stats["users"] = len(ctx.user_ids)
    ctx.stats["items"] = len(ctx.item_ids)
    ctx.stats["sources"] = len(ctx.source_ids)


def _generate_organizations(conn: sqlite3.Connection, ctx: GenerationContext) -> None:
    rows = []
    end = simulation_end()
    for i in range(ctx.scale.n_orgs):
        org_id = f"org_{i:04d}"
        ctx.org_ids.append(org_id)
        parent = None
        if i > 5 and ctx.rng.random() < 0.15:
            parent = ctx.rng.choice(ctx.org_ids[:i])
        org_type = ctx.rng.choice(["company", "studio", "workspace", "publisher"])
        created = random_date_after(SIMULATION_START, end, ctx.rng)
        rows.append((org_id, f"Organization {i}", org_type, parent, to_iso(created)))

    conn.executemany(
        "INSERT INTO organizations VALUES (?,?,?,?,?)",
        rows,
    )


def _generate_users(conn: sqlite3.Connection, ctx: GenerationContext) -> None:
    end = simulation_end()
    active_cutoff = end
    rows = []
    org_weights = ctx.rng.power(1.2, ctx.scale.n_orgs)
    org_probs = org_weights / org_weights.sum()

    for i in range(ctx.scale.n_users):
        user_id = f"usr_{i:05d}"
        ctx.user_ids.append(user_id)
        org_idx = int(ctx.rng.choice(len(ctx.org_ids), p=org_probs))
        org_id = ctx.org_ids[org_idx]
        join = growth_curve_join_date(ctx.rng.random(), ctx.rng)
        propensity = float(ctx.rng.lognormal(mean=0.0, sigma=0.7))
        taste = int(ctx.rng.integers(0, ctx.scale.n_taste_clusters))
        is_active = ctx.rng.random() < ctx.scale.active_user_fraction
        if is_active:
            days_ago = int(ctx.rng.integers(0, ACTIVE_THRESHOLD_DAYS))
            last_active = end - timedelta(days=days_ago)
        else:
            days_ago = int(ctx.rng.integers(ACTIVE_THRESHOLD_DAYS + 1, 400))
            last_active = end - timedelta(days=days_ago)

        ctx.user_org[user_id] = org_id
        ctx.user_join[user_id] = join
        ctx.user_last_active[user_id] = last_active
        ctx.user_propensity[user_id] = propensity
        ctx.user_taste[user_id] = taste
        ctx.user_active[user_id] = is_active
        ctx.adjacency[user_id] = set()

        rows.append(
            (
                user_id,
                org_id,
                f"User {i}",
                to_iso(join),
                to_iso(last_active),
                propensity,
                taste,
                1 if is_active else 0,
            )
        )

    conn.executemany(
        "INSERT INTO users VALUES (?,?,?,?,?,?,?,?)",
        rows,
    )


def _generate_items(conn: sqlite3.Connection, ctx: GenerationContext) -> None:
    end = simulation_end()
    rows = []
    for i in range(ctx.scale.n_items):
        item_id = f"itm_{i:04d}"
        ctx.item_ids.append(item_id)
        popularity = float(ctx.rng.pareto(1.5) + 0.5)
        taste = int(ctx.rng.integers(0, ctx.scale.n_taste_clusters))
        release = random_date_after(SIMULATION_START, end, ctx.rng)
        tags = json.dumps([ctx.rng.choice(["action", "strategy", "casual", "rpg", "sports"])])
        ctx.item_popularity[item_id] = popularity
        ctx.item_taste[item_id] = taste
        ctx.item_release[item_id] = release
        rows.append(
            (
                item_id,
                f"Item {i}",
                f"Provider {taste % 20}",
                tags,
                to_iso(release),
                popularity,
                taste,
            )
        )

    conn.executemany("INSERT INTO items VALUES (?,?,?,?,?,?,?)", rows)


def _generate_sources(conn: sqlite3.Connection, ctx: GenerationContext) -> None:
    end = simulation_end()
    rows = []
    for i in range(ctx.scale.n_sources):
        source_id = f"src_{i:03d}"
        ctx.source_ids.append(source_id)
        spec = int(ctx.rng.integers(0, ctx.scale.n_taste_clusters))
        ctx.source_specialization[source_id] = spec
        created = random_date_after(SIMULATION_START, end, ctx.rng)
        source_type = ctx.rng.choice(["curator", "expert", "creator", "internal"])
        rows.append((source_id, f"Source {i}", source_type, spec, to_iso(created), None))

    conn.executemany("INSERT INTO trusted_sources VALUES (?,?,?,?,?,?)", rows)
