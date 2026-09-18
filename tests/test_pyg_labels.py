"""Tests for Phase 2 label derivation from existing DB (no regeneration)."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import networkx as nx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.pyg.dataset import load_cascade_risk_labels, load_influenced_adoption_labels
from analytics.utils import to_simple_graph


def test_cascade_risk_labels_from_toy_graph(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE users (user_id TEXT, is_active INTEGER);
        CREATE TABLE churn_events (user_id TEXT);
        INSERT INTO users VALUES ('a', 1), ('b', 1), ('c', 1), ('d', 0), ('e', 0);
        INSERT INTO churn_events VALUES ('d'), ('e');
        """
    )

    g = nx.Graph()
    g.add_edges_from([("a", "d"), ("a", "e"), ("b", "d"), ("c", "b")])

    monkeypatch.setattr("analytics.pyg.dataset.load_graph", lambda _layer: g)
    labels = load_cascade_risk_labels(conn, min_churned_neighbors=1, positive_fraction=0.34)
    conn.close()

    risk = dict(zip(labels["user_id"], labels["cascade_risk"]))
    assert risk["a"] == 1
    assert risk["b"] == 1
    assert risk["c"] == 0


def test_influenced_adoption_labels_join():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE user_item_interactions (
            user_id TEXT, item_id TEXT, usage_total REAL
        );
        CREATE TABLE influence_outcomes (
            rule_id TEXT, source_user_id TEXT, target_user_id TEXT
        );
        INSERT INTO user_item_interactions VALUES ('u2', 'i1', 1.0), ('u3', 'i2', 1.0);
        INSERT INTO influence_outcomes VALUES ('rule_adoption', 'u1', 'u2');
        INSERT INTO influence_outcomes VALUES ('rule_participation', 'u1', 'u3');
        """
    )
    labels = load_influenced_adoption_labels(conn)
    conn.close()
    assert len(labels) == 1
    assert labels.iloc[0]["user_id"] == "u2"
    assert labels.iloc[0]["item_id"] == "i1"
