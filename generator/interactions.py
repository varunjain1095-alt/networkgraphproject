"""Layer 3 — user-item interactions."""

from __future__ import annotations

import sqlite3

import numpy as np

from generator.context import GenerationContext
from generator.time_utils import random_datetime_after, simulation_end, to_iso


def generate_interactions(conn: sqlite3.Connection, ctx: GenerationContext) -> None:
    items = ctx.item_ids
    item_pop = np.array([ctx.item_popularity[i] for i in items], dtype=float)
    item_pop /= item_pop.sum()
    item_taste = np.array([ctx.item_taste[i] for i in items], dtype=int)

    interaction_types = ["own", "use", "purchase"]
    type_weights = [0.35, 0.45, 0.20]

    rows = []
    end = simulation_end()

    for user_id in ctx.user_ids:
        n_items = int(ctx.rng.integers(15, 41))
        taste = ctx.user_taste[user_id]
        taste_bonus = np.where(item_taste == taste, 2.0, 1.0)
        probs = item_pop * taste_bonus
        probs /= probs.sum()
        chosen_idx = ctx.rng.choice(len(items), size=n_items, replace=False, p=probs)

        for idx in chosen_idx:
            item_id = items[int(idx)]
            release = ctx.item_release[item_id]
            join = ctx.user_join[user_id]
            start = max(release, join)
            if start > end:
                continue
            itype = str(ctx.rng.choice(interaction_types, p=type_weights))
            idate = random_datetime_after(start, end, ctx.rng)
            usage = float(ctx.rng.lognormal(1.0, 0.5))
            txn = float(ctx.rng.uniform(5, 80)) if itype == "purchase" else None
            rows.append((user_id, item_id, itype, to_iso(idate), usage, txn))

            if len(rows) >= 5000:
                _flush(conn, rows)
                rows.clear()

    if rows:
        _flush(conn, rows)

    ctx.stats["user_item_interactions"] = _count(conn, "user_item_interactions")


def _flush(conn: sqlite3.Connection, rows: list) -> None:
    conn.executemany(
        "INSERT INTO user_item_interactions (user_id, item_id, interaction_type, interaction_date, usage_total, transaction_value) VALUES (?,?,?,?,?,?)",
        rows,
    )


def _count(conn: sqlite3.Connection, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
