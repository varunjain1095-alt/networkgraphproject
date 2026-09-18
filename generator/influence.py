"""Planted influence rules and outcome simulation."""

from __future__ import annotations

import json
import sqlite3
from datetime import timedelta

from generator.context import GenerationContext
from generator.time_utils import random_datetime_after, simulation_end, to_iso


RULE_TEMPLATES = [
    {
        "rule_id": "rule_adoption",
        "influence_family": "adoption",
        "trigger_event": "purchase",
        "eligible_edge_types": json.dumps(["friend", "follow"]),
        "effect_boost": 0.18,
        "base_probability": 0.04,
        "decay_window_days": 14,
        "max_hops": 1,
        "org_constraint": None,
        "outcome_event_type": "purchase",
    },
    {
        "rule_id": "rule_participation",
        "influence_family": "participation",
        "trigger_event": "community_post",
        "eligible_edge_types": json.dumps(["friend", "collaborate"]),
        "effect_boost": 0.15,
        "base_probability": 0.05,
        "decay_window_days": 21,
        "max_hops": 1,
        "org_constraint": None,
        "outcome_event_type": "community_post",
    },
    {
        "rule_id": "rule_activity",
        "influence_family": "activity",
        "trigger_event": "session_join",
        "eligible_edge_types": json.dumps(["friend", "collaborate"]),
        "effect_boost": 0.12,
        "base_probability": 0.06,
        "decay_window_days": 7,
        "max_hops": 1,
        "org_constraint": None,
        "outcome_event_type": "session_join",
    },
    {
        "rule_id": "rule_source",
        "influence_family": "source",
        "trigger_event": "source_recommendation",
        "eligible_edge_types": json.dumps(["follow"]),
        "effect_boost": 0.20,
        "base_probability": 0.03,
        "decay_window_days": 30,
        "max_hops": 1,
        "org_constraint": None,
        "outcome_event_type": "item_adoption",
    },
    {
        "rule_id": "rule_contributor",
        "influence_family": "contributor",
        "trigger_event": "contribution_validation",
        "eligible_edge_types": json.dumps(["friend", "collaborate"]),
        "effect_boost": 0.16,
        "base_probability": 0.04,
        "decay_window_days": 14,
        "max_hops": 1,
        "org_constraint": None,
        "outcome_event_type": "contribution",
    },
]


def generate_influence(conn: sqlite3.Connection, ctx: GenerationContext) -> None:
    end = simulation_end()
    rule_rows = []
    for tmpl in RULE_TEMPLATES:
        rule_rows.append(
            (
                tmpl["rule_id"],
                tmpl["influence_family"],
                tmpl["trigger_event"],
                tmpl["eligible_edge_types"],
                tmpl["effect_boost"],
                tmpl["base_probability"],
                tmpl["decay_window_days"],
                tmpl["max_hops"],
                tmpl["org_constraint"],
                ctx.seed,
                to_iso(end),
            )
        )
    conn.executemany(
        "INSERT INTO planted_influence_rules VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        rule_rows,
    )

    outcome_rows = []
    sample_users = ctx.rng.choice(ctx.user_ids, size=min(800, len(ctx.user_ids)), replace=False)
    for source_user in sample_users:
        neighbors = list(ctx.neighbors(source_user))
        if not neighbors:
            continue
        rule = RULE_TEMPLATES[int(ctx.rng.integers(0, len(RULE_TEMPLATES)))]
        for target in ctx.rng.choice(neighbors, size=min(3, len(neighbors)), replace=False):
            if ctx.rng.random() > rule["base_probability"] + rule["effect_boost"]:
                continue
            start = max(ctx.user_join[source_user], ctx.user_join[str(target)])
            ts = random_datetime_after(start, end, ctx.rng)
            edge_type = json.loads(rule["eligible_edge_types"])[0]
            outcome_rows.append(
                (
                    rule["rule_id"],
                    source_user,
                    str(target),
                    edge_type,
                    rule["outcome_event_type"],
                    to_iso(ts),
                    None,
                )
            )

    conn.executemany(
        "INSERT INTO influence_outcomes (rule_id, source_user_id, target_user_id, edge_type_used, outcome_event_type, outcome_timestamp, reference_entity_id) VALUES (?,?,?,?,?,?,?)",
        outcome_rows,
    )
    ctx.stats["planted_influence_rules"] = len(RULE_TEMPLATES)
    ctx.stats["influence_outcomes"] = len(outcome_rows)
