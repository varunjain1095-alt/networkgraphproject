"""Layer 2 — activity sessions and participants."""

from __future__ import annotations

import sqlite3
from collections import defaultdict

from generator.context import GenerationContext
from generator.time_utils import random_datetime_after, simulation_end, to_iso


def generate_activities(conn: sqlite3.Connection, ctx: GenerationContext) -> None:
    target_sessions = int(ctx.rng.integers(ctx.scale.min_sessions, ctx.scale.max_sessions + 1))
    items = ctx.item_ids
    item_by_taste: dict[int, list[str]] = defaultdict(list)
    for item_id in items:
        item_by_taste[ctx.item_taste[item_id]].append(item_id)

    session_rows: list[tuple] = []
    participant_rows: list[tuple] = []
    end = simulation_end()
    active_users = [u for u in ctx.user_ids if ctx.user_active[u]] or ctx.user_ids

    for session_counter in range(target_sessions):
        host = str(ctx.rng.choice(active_users))
        taste = ctx.user_taste[host]
        taste_items = item_by_taste.get(taste, items)
        item_id = str(ctx.rng.choice(taste_items))
        join = ctx.user_join[host]
        release = ctx.item_release[item_id]
        start = max(join, release)
        if start > end:
            continue

        session_id = f"sess_{session_counter:07d}"
        ts = random_datetime_after(start, end, ctx.rng)
        duration = int(ctx.rng.integers(300, 7200))
        session_rows.append((session_id, item_id, "coplay", to_iso(ts), duration, "within_org"))

        n_part = int(ctx.rng.integers(2, 9))
        participants = {host}
        neighbors = list(ctx.neighbors(host))
        if neighbors and ctx.rng.random() < 0.75:
            pick = min(n_part - 1, len(neighbors))
            for nb in ctx.rng.choice(neighbors, size=pick, replace=False):
                participants.add(str(nb))
        while len(participants) < n_part:
            extra = str(ctx.rng.choice(active_users))
            participants.add(extra)

        for user_id in participants:
            if ctx.user_join[user_id] > ts.date():
                continue
            role = "host" if user_id == host else "participant"
            participant_rows.append((session_id, user_id, role))

        if len(session_rows) >= 5000:
            _flush_sessions(conn, session_rows, participant_rows)
            session_rows.clear()
            participant_rows.clear()

    if session_rows:
        _flush_sessions(conn, session_rows, participant_rows)

    ctx.stats["activity_sessions"] = _count(conn, "activity_sessions")
    ctx.stats["activity_session_participants"] = _count(conn, "activity_session_participants")


def _flush_sessions(
    conn: sqlite3.Connection,
    sessions: list,
    participants: list,
) -> None:
    conn.executemany("INSERT INTO activity_sessions VALUES (?,?,?,?,?,?)", sessions)
    conn.executemany("INSERT INTO activity_session_participants VALUES (?,?,?)", participants)


def _count(conn: sqlite3.Connection, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
