"""Layer 4 — contributions, validations, source follows and recommendations."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime

import numpy as np

from generator.context import GenerationContext
from generator.time_utils import random_datetime_after, simulation_end, to_iso


def generate_layer4(conn: sqlite3.Connection, ctx: GenerationContext) -> None:
    _generate_contributions(conn, ctx)
    _generate_source_follows(conn, ctx)
    _generate_source_recommendations(conn, ctx)
    ctx.stats["contributions"] = _count(conn, "contributions")
    ctx.stats["contribution_validation_events"] = _count(conn, "contribution_validation_events")
    ctx.stats["source_follows"] = _count(conn, "source_follows")
    ctx.stats["source_recommendations"] = _count(conn, "source_recommendations")


def _generate_contributions(conn: sqlite3.Connection, ctx: GenerationContext) -> None:
    total = conn.execute("SELECT COUNT(*) FROM user_item_interactions").fetchone()[0]
    if total == 0:
        return

    sample_size = max(1, int(total * ctx.rng.uniform(0.05, 0.10)))
    rows = conn.execute(
        f"""
        SELECT interaction_id, user_id, item_id, interaction_date
        FROM user_item_interactions
        ORDER BY RANDOM()
        LIMIT {sample_size}
        """
    ).fetchall()

    contrib_rows = []
    validation_rows = []
    end = simulation_end()

    for _, user_id, item_id, idate in rows:
        quality = float(ctx.rng.beta(2, 5))
        idate_dt = datetime.fromisoformat(idate.replace("Z", ""))
        ts = random_datetime_after(idate_dt.date(), end, ctx.rng)
        cid = f"contrib_{uuid.uuid4().hex[:10]}"
        rating = round(float(ctx.rng.uniform(1, 5)), 1)
        contrib_rows.append((cid, user_id, item_id, f"Review for {item_id}", rating, to_iso(ts), quality))

        n_votes = int(ctx.rng.poisson(2 + quality * 6))
        voters = _pick_voters(ctx, user_id, n_votes)
        for voter in voters:
            vtype = str(ctx.rng.choice(["helpful", "endorse", "verify"]))
            vts = random_datetime_after(ts.date(), end, ctx.rng)
            validation_rows.append((cid, voter, vtype, to_iso(vts)))

        if len(contrib_rows) >= 2000:
            _flush_contrib(conn, contrib_rows, validation_rows)
            contrib_rows.clear()
            validation_rows.clear()

    if contrib_rows:
        _flush_contrib(conn, contrib_rows, validation_rows)


def _pick_voters(ctx: GenerationContext, contributor: str, n: int) -> list[str]:
    neighbors = list(ctx.neighbors(contributor))
    pool = neighbors if neighbors else ctx.user_ids
    n = min(n, len(pool))
    if n == 0:
        return []
    return [str(v) for v in ctx.rng.choice(pool, size=n, replace=False)]


def _generate_source_follows(conn: sqlite3.Connection, ctx: GenerationContext) -> None:
    source_weights = np.array(
        [1.0 / (i + 1) ** 0.8 for i in range(len(ctx.source_ids))], dtype=float
    )
    source_weights /= source_weights.sum()
    end = simulation_end()
    rows = []

    for user_id in ctx.user_ids:
        n_follows = int(ctx.rng.integers(3, 9))
        sources = ctx.rng.choice(ctx.source_ids, size=n_follows, replace=False, p=source_weights)
        join = ctx.user_join[user_id]
        for source_id in sources:
            follow_date = random_datetime_after(join, end, ctx.rng)
            rows.append((user_id, str(source_id), to_iso(follow_date)))
            if len(rows) >= 5000:
                conn.executemany("INSERT INTO source_follows VALUES (?,?,?)", rows)
                rows.clear()

    if rows:
        conn.executemany("INSERT INTO source_follows VALUES (?,?,?)", rows)


def _generate_source_recommendations(conn: sqlite3.Connection, ctx: GenerationContext) -> None:
    end = simulation_end()
    rows = []
    items_by_taste: dict[int, list[str]] = {}
    for item_id in ctx.item_ids:
        items_by_taste.setdefault(ctx.item_taste[item_id], []).append(item_id)

    for source_id in ctx.source_ids:
        spec = ctx.source_specialization[source_id]
        candidates = items_by_taste.get(spec, ctx.item_ids)
        n_recs = int(ctx.rng.integers(10, 40))
        chosen = ctx.rng.choice(candidates, size=min(n_recs, len(candidates)), replace=False)
        for item_id in chosen:
            release = ctx.item_release[item_id]
            rec_date = random_datetime_after(release, end, ctx.rng)
            rows.append((source_id, item_id, to_iso(rec_date)))
            if len(rows) >= 3000:
                conn.executemany(
                    "INSERT INTO source_recommendations (source_id, item_id, recommendation_date) VALUES (?,?,?)",
                    rows,
                )
                rows.clear()

    if rows:
        conn.executemany(
            "INSERT INTO source_recommendations (source_id, item_id, recommendation_date) VALUES (?,?,?)",
            rows,
        )


def _flush_contrib(conn, contrib_rows, validation_rows) -> None:
    conn.executemany("INSERT INTO contributions VALUES (?,?,?,?,?,?,?)", contrib_rows)
    conn.executemany(
        "INSERT INTO contribution_validation_events (contribution_id, voter_user_id, validation_type, validation_timestamp) VALUES (?,?,?,?)",
        validation_rows,
    )


def _count(conn: sqlite3.Connection, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
