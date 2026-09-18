"""Influence training should not require both endpoints in the train split."""

from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.pyg.train import _build_balanced_test_pairs


def test_influence_style_train_keeps_source_in_train_only():
    pos = [("s1", "t_test"), ("s2", "t_train"), ("s_test", "t3")]
    pos_set = set(pos)
    train_users = {"s1", "s2", "t_train"}
    test_users = {"t_test", "s_test", "t3"}

    train_pairs = [(s, t, 1) for s, t in pos if s in train_users]
    test_pairs = _build_balanced_test_pairs(
        pos, test_users, ["s1", "s2", "t_test", "t_train", "s_test", "t3"], pos_set, random.Random(0), endpoint="either"
    )

    assert ("s1", "t_test", 1) in train_pairs
    assert ("s2", "t_train", 1) in train_pairs
    assert not any(s == "s_test" for s, _, _ in train_pairs)
    assert test_pairs
    assert any(label == 0 for *_, label in test_pairs)
