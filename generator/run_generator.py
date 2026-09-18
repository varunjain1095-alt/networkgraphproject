"""Orchestrate full synthetic dataset generation."""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.domain import load_domain_config
from config.env import get, load_env, resolve_path
from generator.activities import generate_activities
from generator.context import GenerationContext
from generator.db_utils import clear_generated_data, connect
from generator.influence import generate_influence
from generator.interactions import generate_interactions
from generator.layer4 import generate_layer4
from generator.relationships import generate_relationships
from generator.scale import get_scale
from generator.supporting_events import generate_supporting_events
from generator.time_utils import to_iso
from generator.users import generate_core_entities
from scripts.init_db import init_db


def config_hash() -> str:
    domain_path = Path(__file__).resolve().parents[1] / "domain_config.yaml"
    digest = hashlib.sha256(domain_path.read_bytes()).hexdigest()
    return digest[:16]


def build_context(seed: int, scale_mode: str) -> GenerationContext:
    load_domain_config()
    scale = get_scale(scale_mode)
    rng = np.random.default_rng(seed)
    return GenerationContext(
        rng=rng,
        scale=scale,
        seed=seed,
        scale_mode=scale_mode,
        config_hash=config_hash(),
    )


def run_generation(db_path: Path, seed: int, scale_mode: str, force_schema: bool = False) -> GenerationContext:
    if force_schema or not db_path.exists():
        init_db(db_path=db_path, force=True)
    else:
        init_db(db_path=db_path, force=False)

    ctx = build_context(seed, scale_mode)
    conn = connect(db_path)

    try:
        print(f"Generating synthetic data (scale={scale_mode}, seed={seed})...")
        t0 = time.time()
        clear_generated_data(conn)
        conn.commit()

        print(f"  1A.1 Core entities...", flush=True)
        generate_core_entities(conn, ctx)
        conn.commit()

        print(f"  1A.2 Relationships...", flush=True)
        generate_relationships(conn, ctx)
        conn.commit()

        print(f"  1A.3 User-item interactions...", flush=True)
        generate_interactions(conn, ctx)
        conn.commit()

        print(f"  1A.4 Activity sessions...", flush=True)
        generate_activities(conn, ctx)
        conn.commit()

        print(f"  1A.5 Layer 4 (contributions, sources)...", flush=True)
        generate_layer4(conn, ctx)
        conn.commit()

        print(f"  1A.6 Planted influence rules...", flush=True)
        generate_influence(conn, ctx)
        conn.commit()

        print(f"  1A.7 Supporting events...", flush=True)
        generate_supporting_events(conn, ctx)
        conn.commit()

        edge_count = conn.execute("SELECT COUNT(*) FROM relationship_edges").fetchone()[0]
        session_count = conn.execute("SELECT COUNT(*) FROM activity_sessions").fetchone()[0]
        conn.execute("DELETE FROM dataset_metadata")
        conn.execute(
            "INSERT INTO dataset_metadata VALUES (1,?,?,?,?,?,?,?,?)",
            (
                to_iso(datetime.now(timezone.utc)),
                seed,
                ctx.config_hash,
                scale_mode,
                "1.0.0",
                len(ctx.user_ids),
                edge_count,
                session_count,
            ),
        )
        conn.commit()

        elapsed = time.time() - t0
        print(f"Generation complete in {elapsed:.1f}s")
        _print_summary(conn, ctx)
        return ctx
    finally:
        conn.close()


def _print_summary(conn, ctx: GenerationContext) -> None:
    tables = [
        "organizations",
        "users",
        "items",
        "trusted_sources",
        "relationship_edges",
        "referrals",
        "user_item_interactions",
        "activity_sessions",
        "activity_session_participants",
        "contributions",
        "contribution_validation_events",
        "source_follows",
        "source_recommendations",
        "planted_influence_rules",
        "influence_outcomes",
        "community_participation",
        "support_tickets",
        "feature_exposure_log",
        "churn_events",
        "onboarding_events",
    ]
    print("\nRow counts:")
    for table in tables:
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {n:,}")


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Generate synthetic network graph dataset")
    parser.add_argument("--seed", type=int, default=int(get("GENERATOR_SEED", "42") or 42))
    parser.add_argument("--scale", default=get("SCALE_MODE", "demo") or "demo")
    parser.add_argument("--force-schema", action="store_true", help="Recreate DB schema before generate")
    args = parser.parse_args()

    db_path = resolve_path("DATABASE_PATH", "data/synthetic.db")
    try:
        run_generation(db_path, args.seed, args.scale, force_schema=args.force_schema)
        return 0
    except Exception as exc:
        print(f"Generation FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
