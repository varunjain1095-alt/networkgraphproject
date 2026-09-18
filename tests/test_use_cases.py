"""Phase 1D use case engine tests."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def pipeline_env(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("uc") / "test.db"
    graphs_dir = tmp_path_factory.mktemp("g") / "graphs"
    metrics_dir = tmp_path_factory.mktemp("m") / "metrics"
    env = {
        **__import__("os").environ,
        "DATABASE_PATH": str(db_path),
        "GRAPHS_DIR": str(graphs_dir),
        "METRICS_DIR": str(metrics_dir),
    }

    for script in (
        [ROOT / "generator" / "run_generator.py", "--scale", "dev", "--seed", "5", "--force-schema"],
        [ROOT / "graphs" / "builder.py", "--all-layers"],
        [ROOT / "analytics" / "networkx_metrics.py"],
    ):
        r = subprocess.run([sys.executable, str(script[0]), *script[1:]], cwd=ROOT, env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr + r.stdout

    return db_path, env


def test_all_use_cases_produce_output(pipeline_env):
    sys.path.insert(0, str(ROOT))
    from use_cases.context import UseCaseContext
    from use_cases.registry import run_all

    db_path, _ = pipeline_env
    with UseCaseContext(sqlite3.connect(db_path)) as ctx:
        ctx.conn.row_factory = sqlite3.Row
        results = run_all(ctx)

    assert len(results) == 8
    for uc_id, result in results.items():
        assert result.use_case_id == uc_id
        assert result.title
        if not result.has_results:
            assert result.empty_message, f"{uc_id} missing empty_message"


def test_explanations_plain_english(pipeline_env):
    sys.path.insert(0, str(ROOT))
    from use_cases.context import UseCaseContext
    from use_cases.registry import run_all

    db_path, _ = pipeline_env
    with UseCaseContext(sqlite3.connect(db_path)) as ctx:
        ctx.conn.row_factory = sqlite3.Row
        results = run_all(ctx)

    for result in results.values():
        for item in result.flagged:
            assert item.explanation
            assert item.recommended_action
            assert "eigenvector_centrality" not in item.explanation.lower()


def test_churn_excludes_churned_users(pipeline_env):
    sys.path.insert(0, str(ROOT))
    from use_cases.champion_churn import ChampionChurnUseCase
    from use_cases.context import UseCaseContext

    db_path, _ = pipeline_env
    with UseCaseContext(sqlite3.connect(db_path)) as ctx:
        ctx.conn.row_factory = sqlite3.Row
        result = ChampionChurnUseCase().run(ctx)
        churned = ctx.churned_user_ids()
        flagged_ids = {f.node_id for f in result.flagged}
        assert flagged_ids.isdisjoint(churned)


def test_ab_contamination_tiered(pipeline_env):
    sys.path.insert(0, str(ROOT))
    from use_cases.ab_contamination import ABContaminationUseCase
    from use_cases.context import UseCaseContext

    db_path, _ = pipeline_env
    with UseCaseContext(sqlite3.connect(db_path)) as ctx:
        ctx.conn.row_factory = sqlite3.Row
        result = ABContaminationUseCase().run(ctx)

    if len(result.flagged) >= 2:
        tiers = [f.extra.get("tier") for f in result.flagged]
        if "high" in tiers and "low" in tiers:
            high = next(f for f in result.flagged if f.extra.get("tier") == "high")
            low = next(f for f in result.flagged if f.extra.get("tier") == "low")
            assert high.score > low.score


def test_onboarding_active_connection(pipeline_env):
    sys.path.insert(0, str(ROOT))
    from use_cases.context import UseCaseContext
    from use_cases.onboarding_flow import OnboardingFlowUseCase

    db_path, _ = pipeline_env
    with UseCaseContext(sqlite3.connect(db_path)) as ctx:
        ctx.conn.row_factory = sqlite3.Row
        result = OnboardingFlowUseCase().run(ctx)
        for item in result.flagged:
            if item.metrics.get("has_active_connection") == 0.0:
                assert "guided" in item.explanation.lower() or "guided" in item.recommended_action.lower()


def test_research_uses_validated_influence(pipeline_env):
    sys.path.insert(0, str(ROOT))
    from use_cases.context import UseCaseContext
    from use_cases.research_priority import ResearchPriorityUseCase

    db_path, _ = pipeline_env
    with UseCaseContext(sqlite3.connect(db_path)) as ctx:
        ctx.conn.row_factory = sqlite3.Row
        result = ResearchPriorityUseCase().run(ctx)

    for item in result.flagged[:5]:
        assert "community-validated" in item.explanation.lower() or "validated" in item.explanation.lower()
        assert item.metrics.get("community_validated_influence", 0) >= 0


def test_toggle_supports_least(pipeline_env):
    sys.path.insert(0, str(ROOT))
    from use_cases.context import UseCaseContext
    from use_cases.rollout_sequencing import RolloutSequencingUseCase

    db_path, _ = pipeline_env
    with UseCaseContext(sqlite3.connect(db_path)) as ctx:
        ctx.conn.row_factory = sqlite3.Row
        most = RolloutSequencingUseCase().run(ctx, most_important=True)
        least = RolloutSequencingUseCase().run(ctx, most_important=False)

    if len(most.flagged) >= 2:
        assert most.flagged[0].score >= most.flagged[-1].score
        assert least.flagged[0].score <= least.flagged[-1].score
