"""Layer 1 — relationship edges and referrals."""

from __future__ import annotations

import sqlite3

import numpy as np

from generator.context import GenerationContext
from generator.time_utils import random_datetime_after, simulation_end, to_iso


def generate_relationships(conn: sqlite3.Connection, ctx: GenerationContext) -> None:
    target = int(ctx.rng.integers(ctx.scale.min_relationship_edges, ctx.scale.max_relationship_edges + 1))
    _generate_relationship_edges(conn, ctx, target)
    _generate_referrals(conn, ctx)
    _plant_fraud_ring(conn, ctx)
    ctx.stats["relationship_edges"] = len(ctx.relationship_pairs)


def _generate_relationship_edges(
    conn: sqlite3.Connection, ctx: GenerationContext, target: int
) -> None:
    users = ctx.user_ids
    n = len(users)
    prop = np.array([ctx.user_propensity[u] for u in users], dtype=float)
    prop /= prop.sum()

    # Lognormal target degrees — hubs get 50-100+, most users 5-15
    degrees = np.clip(ctx.rng.lognormal(mean=2.2, sigma=0.55, size=n).astype(int), 3, 100)
    total_stubs = int(degrees.sum())
    if total_stubs < target * 2:
        scale = (target * 2) / total_stubs
        degrees = np.clip((degrees * scale).astype(int), 3, 100)

    rel_types = ["friend", "follow", "collaborate", "member_of"]
    type_weights = np.array([0.55, 0.25, 0.15, 0.05])

    rows: list[tuple] = []
    end = simulation_end()

    for idx, user_a in enumerate(users):
        need = int(degrees[idx])
        candidates = ctx.rng.choice(n, size=min(need * 3, n), replace=False, p=prop)
        added = 0
        for cidx in candidates:
            if added >= need:
                break
            user_b = users[int(cidx)]
            if user_a == user_b:
                continue
            rel_type = str(ctx.rng.choice(rel_types, p=type_weights))
            if rel_type in ("friend", "collaborate"):
                a, b = sorted((user_a, user_b))
            else:
                a, b = user_a, user_b
            key = (a, b, rel_type)
            if key in ctx.relationship_pairs:
                continue

            join_a = ctx.user_join[user_a]
            join_b = ctx.user_join[user_b]
            start = max(join_a, join_b)
            if start > end:
                continue
            conn_date = random_datetime_after(start, end, ctx.rng)
            scope = "within_org" if ctx.user_org[user_a] == ctx.user_org[user_b] else "cross_org"
            ctx.add_edge(user_a, user_b, rel_type)
            rows.append((a, b, rel_type, to_iso(conn_date), scope))
            added += 1

            if len(rows) >= 10000:
                conn.executemany(
                    "INSERT INTO relationship_edges (user_id_a, user_id_b, relationship_type, connection_date, organization_scope) VALUES (?,?,?,?,?)",
                    rows,
                )
                rows.clear()

    if rows:
        conn.executemany(
            "INSERT INTO relationship_edges (user_id_a, user_id_b, relationship_type, connection_date, organization_scope) VALUES (?,?,?,?,?)",
            rows,
        )


def _generate_referrals(conn: sqlite3.Connection, ctx: GenerationContext) -> None:
    n_referrals = int(len(ctx.user_ids) * ctx.scale.referral_rate)
    referred = ctx.rng.choice(ctx.user_ids, size=n_referrals, replace=False)
    rows = []
    for referred_user in referred:
        referrer = str(ctx.rng.choice(ctx.user_ids))
        if referrer == referred_user:
            continue
        ref_time = random_datetime_after(
            ctx.user_join[referrer],
            ctx.user_join[referred_user],
            ctx.rng,
        )
        source = str(ctx.rng.choice(["internal", "external", "campaign"]))
        rows.append((referred_user, referrer, source, to_iso(ref_time)))

    conn.executemany(
        "INSERT INTO referrals (referred_user_id, referrer_user_id, referral_source, referral_timestamp) VALUES (?,?,?,?)",
        rows,
    )


def _plant_fraud_ring(conn: sqlite3.Connection, ctx: GenerationContext) -> None:
    """Dense reciprocal cluster for fraud detection use case."""
    ring_size = min(20, len(ctx.user_ids) // 10)
    if ring_size < 5:
        return
    ring = list(ctx.rng.choice(ctx.user_ids, size=ring_size, replace=False))
    extra = []
    end = simulation_end()
    for i, user_a in enumerate(ring):
        for user_b in ring[i + 1 :]:
            for rel_type in ("friend", "collaborate"):
                a, b = sorted((user_a, user_b))
                key = (a, b, rel_type)
                if key in ctx.relationship_pairs:
                    continue
                start = max(ctx.user_join[user_a], ctx.user_join[user_b])
                conn_date = random_datetime_after(start, end, ctx.rng)
                ctx.add_edge(user_a, user_b, rel_type)
                extra.append((a, b, rel_type, to_iso(conn_date), "within_org"))

    if extra:
        conn.executemany(
            "INSERT INTO relationship_edges (user_id_a, user_id_b, relationship_type, connection_date, organization_scope) VALUES (?,?,?,?,?)",
            extra,
        )
