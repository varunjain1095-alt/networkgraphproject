"""Supporting event tables for use cases."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import timedelta

from generator.context import GenerationContext
from generator.time_utils import (
    ACTIVE_THRESHOLD_DAYS,
    random_datetime_after,
    simulation_end,
    to_iso,
)


def generate_supporting_events(conn: sqlite3.Connection, ctx: GenerationContext) -> None:
    end = simulation_end()
    _community_participation(conn, ctx, end)
    _support_tickets(conn, ctx, end)
    _feature_exposure(conn, ctx, end)
    _churn_events(conn, ctx, end)
    _onboarding_events(conn, ctx, end)
    _trust_safety(conn, ctx, end)


def _community_participation(conn, ctx, end) -> None:
    rows = []
    sample = ctx.rng.choice(ctx.user_ids, size=min(len(ctx.user_ids), int(len(ctx.user_ids) * 0.4)), replace=False)
    for user_id in sample:
        n_posts = int(ctx.rng.integers(1, 6))
        for _ in range(n_posts):
            ts = random_datetime_after(ctx.user_join[user_id], end, ctx.rng)
            rows.append((f"post_{uuid.uuid4().hex[:10]}", user_id, to_iso(ts), int(ctx.rng.integers(0, 200)), "general"))
            if len(rows) >= 5000:
                conn.executemany("INSERT INTO community_participation VALUES (?,?,?,?,?)", rows)
                rows.clear()
    if rows:
        conn.executemany("INSERT INTO community_participation VALUES (?,?,?,?,?)", rows)


def _support_tickets(conn, ctx, end) -> None:
    rows = []
    sample = ctx.rng.choice(ctx.user_ids, size=min(2000, len(ctx.user_ids) // 5), replace=False)
    for user_id in sample:
        ts = random_datetime_after(ctx.user_join[user_id], end, ctx.rng)
        severity = str(ctx.rng.choice(["low", "medium", "high", "critical"], p=[0.4, 0.35, 0.2, 0.05]))
        rows.append((f"tkt_{uuid.uuid4().hex[:8]}", user_id, to_iso(ts), severity, "open", "bug"))
    conn.executemany("INSERT INTO support_tickets VALUES (?,?,?,?,?,?)", rows)


def _feature_exposure(conn, ctx, end) -> None:
    experiment_id = "exp_rollout_001"
    feature_id = "feat_discovery_v2"
    rows = []
    for user_id in ctx.user_ids:
        variant = "treatment" if ctx.rng.random() < 0.5 else "control"
        ts = random_datetime_after(ctx.user_join[user_id], end, ctx.rng)
        exposed = 1 if ctx.rng.random() < 0.7 else 0
        rows.append((user_id, feature_id, experiment_id, variant, exposed, to_iso(ts)))
        if len(rows) >= 8000:
            conn.executemany(
                "INSERT INTO feature_exposure_log (user_id, feature_id, experiment_id, variant, exposed_flag, exposure_timestamp) VALUES (?,?,?,?,?,?)",
                rows,
            )
            rows.clear()
    if rows:
        conn.executemany(
            "INSERT INTO feature_exposure_log (user_id, feature_id, experiment_id, variant, exposed_flag, exposure_timestamp) VALUES (?,?,?,?,?,?)",
            rows,
        )


def _churn_events(conn, ctx, end) -> None:
    churned = [u for u in ctx.user_ids if not ctx.user_active[u]]
    rows = []
    for user_id in churned:
        churn_date = ctx.user_last_active[user_id]
        rows.append((user_id, to_iso(churn_date), to_iso(churn_date), "voluntary"))
    conn.executemany("INSERT INTO churn_events VALUES (?,?,?,?)", rows)


def _onboarding_events(conn, ctx, end) -> None:
    rows = []
    cutoff = end - timedelta(days=ACTIVE_THRESHOLD_DAYS)
    recent_users = [u for u in ctx.user_ids if ctx.user_join[u] >= end - timedelta(days=365)]
    for user_id in recent_users:
        had_active = _has_active_connection(ctx, user_id, cutoff)
        flow = "guided" if had_active else "self_service"
        ts = random_datetime_after(ctx.user_join[user_id], end, ctx.rng)
        status = str(ctx.rng.choice(["completed", "in_progress", "abandoned"], p=[0.6, 0.25, 0.15]))
        rows.append((user_id, flow, to_iso(ts), status, 1 if had_active else 0))
    conn.executemany(
        "INSERT INTO onboarding_events (user_id, onboarding_flow_type, assigned_timestamp, completion_status, had_active_connection_at_start) VALUES (?,?,?,?,?)",
        rows,
    )


def _has_active_connection(ctx: GenerationContext, user_id: str, cutoff) -> bool:
    for neighbor in ctx.neighbors(user_id):
        if ctx.user_active.get(neighbor) and ctx.user_last_active[neighbor] >= cutoff:
            return True
    return False


def _trust_safety(conn, ctx, end) -> None:
    rows = []
    sample = ctx.rng.choice(ctx.user_ids, size=min(500, len(ctx.user_ids) // 20), replace=False)
    for user_id in sample:
        ts = random_datetime_after(ctx.user_join[user_id], end, ctx.rng)
        rows.append((user_id, "policy_violation", str(ctx.rng.choice(["low", "medium", "high"])), to_iso(ts)))
    conn.executemany(
        "INSERT INTO trust_safety_events (user_id, event_type, severity, event_timestamp) VALUES (?,?,?,?)",
        rows,
    )
