"""Replay training with per-epoch loss logging (diagnostic for learning failures)."""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import torch
import torch.nn.functional as F
from torch import optim

from analytics.pyg.dataset import (
    build_adoption_graph,
    build_user_social_graph,
    load_cascade_risk_labels,
    load_influenced_adoption_labels,
    load_influence_edges,
)
from analytics.pyg.models import LinkPredictor, NodeClassifier, require_models
from analytics.pyg.split import community_holdout_split, load_community_map
from analytics.pyg.train import (
    TrainConfig,
    _build_balanced_test_pairs,
    _link_eval_metrics,
    _mask_edge_index,
    _sample_negative_pairs,
)
from analytics.utils import to_simple_graph
from config.env import load_env
from graphs.db import open_db

require_models()


def _grad_norm(model) -> float:
    total = 0.0
    for p in model.parameters():
        if p.grad is not None:
            total += float(p.grad.data.norm(2).item() ** 2)
    return total**0.5


def _feature_stats(x: torch.Tensor) -> dict:
    return {
        "shape": tuple(x.shape),
        "mean": float(x.mean().item()),
        "std": float(x.std().item()),
        "zero_frac": float((x == 0).float().mean().item()),
        "row_std_mean": float(x.std(dim=1).mean().item()),
    }


def _logit_stats(logits: torch.Tensor) -> dict:
    probs = torch.sigmoid(logits)
    return {
        "logit_mean": float(logits.mean().item()),
        "logit_std": float(logits.std().item()),
        "prob_mean": float(probs.mean().item()),
        "pred_pos_rate": float((probs >= 0.5).float().mean().item()),
    }


def diag_adoption(conn, config: TrainConfig) -> None:
    print("\n=== combined_adoption ===", flush=True)
    data, _ = build_adoption_graph(conn)
    labels = load_influenced_adoption_labels(conn)
    print(f"features: {_feature_stats(data.x)}", flush=True)
    print(f"edges: {data.edge_index.shape[1]}", flush=True)

    node_ids = list(data.node_ids)
    index = {n: i for i, n in enumerate(node_ids)}
    graph_nx = __import__("graphs.cache", fromlist=["load_graph"]).load_graph(3)
    item_ids = {str(n) for n, d in graph_nx.nodes(data=True) if d.get("node_type") == "item"}
    user_ids = [n for n in node_ids if n not in item_ids]

    pos_pairs = [(u, i) for u, i in zip(labels["user_id"], labels["item_id"]) if u in index and i in index]
    rng = random.Random(config.seed)
    all_items = list({i for _, i in pos_pairs})
    pos_set = set(pos_pairs)
    neg_pairs = []
    while len(neg_pairs) < len(pos_pairs):
        u, i = rng.choice(user_ids), rng.choice(all_items)
        if (u, i) not in pos_set:
            neg_pairs.append((u, i))

    split_graph = to_simple_graph(__import__("graphs.cache", fromlist=["load_graph"]).load_graph(1))
    comm = load_community_map(conn, "layer1")
    split = community_holdout_split(split_graph, comm, seed=config.seed)
    train_users, test_users = set(split.train_nodes), set(split.test_nodes)

    train_pairs = [(u, i, 1) for u, i in pos_pairs if u in train_users]
    train_pairs += [(u, i, 0) for u, i in neg_pairs if u in train_users]
    test_pairs = _build_balanced_test_pairs(pos_pairs, test_users, all_items, pos_set, rng, endpoint="first")
    holdout_edges = {(u, i) for u, i, label in test_pairs if label == 1}

    print(f"train_pairs={len(train_pairs)} test_pairs={len(test_pairs)} holdout_edges={len(holdout_edges)}", flush=True)

    model = LinkPredictor(int(data.x.shape[1]), config.hidden)
    opt = optim.Adam(model.parameters(), lr=config.lr)
    x = data.x
    edge_index = _mask_edge_index(data.edge_index, node_ids, holdout_edges)

    for epoch in range(1, config.epochs + 1):
        model.train()
        opt.zero_grad()
        src = torch.tensor([index[u] for u, _, _ in train_pairs], dtype=torch.long)
        dst = torch.tensor([index[i] for _, i, _ in train_pairs], dtype=torch.long)
        y = torch.tensor([float(l) for *_, l in train_pairs], dtype=torch.float)
        logits = model(x, edge_index, src, dst)
        loss = F.binary_cross_entropy_with_logits(logits, y)
        loss.backward()
        gnorm = _grad_norm(model)
        opt.step()

        model.eval()
        with torch.no_grad():
            t_src = torch.tensor([index[u] for u, _, _ in test_pairs], dtype=torch.long)
            t_dst = torch.tensor([index[i] for _, i, _ in test_pairs], dtype=torch.long)
            t_y = torch.tensor([float(l) for *_, l in test_pairs], dtype=torch.float)
            t_logits = model(x, edge_index, t_src, t_dst)
            acc, base, rec = _link_eval_metrics(t_logits, t_y)
            lstats = _logit_stats(t_logits)

        print(
            f"  epoch {epoch}: loss={loss.item():.6f} grad_norm={gnorm:.6f} "
            f"test_acc={acc:.4f} baseline={base:.4f} {lstats}",
            flush=True,
        )


def diag_churn(conn, config: TrainConfig) -> None:
    print("\n=== churn_cascade ===", flush=True)
    data, graph = build_user_social_graph(conn)
    labels = load_cascade_risk_labels(conn)
    print(f"features: {_feature_stats(data.x)}", flush=True)
    print(f"edges: {data.edge_index.shape[1]}", flush=True)

    node_ids = list(data.node_ids)
    y = torch.full((len(node_ids),), float("nan"))
    index = {n: i for i, n in enumerate(node_ids)}
    for _, row in labels.iterrows():
        uid = row["user_id"]
        if uid in index:
            y[index[uid]] = float(row["cascade_risk"])

    comm = load_community_map(conn, "layer1")
    split = community_holdout_split(graph, comm, seed=config.seed)
    train_mask = split.train_mask & ~torch.isnan(y)
    test_mask = split.test_mask & ~torch.isnan(y)
    print(f"train_labeled={int(train_mask.sum())} test_labeled={int(test_mask.sum())}", flush=True)

    model = NodeClassifier(int(data.x.shape[1]), config.hidden)
    opt = optim.Adam(model.parameters(), lr=config.lr)
    x, edge_index = data.x, data.edge_index

    for epoch in range(1, config.epochs + 1):
        model.train()
        opt.zero_grad()
        logits = model(x, edge_index)
        loss = F.binary_cross_entropy_with_logits(logits[train_mask], y[train_mask])
        loss.backward()
        gnorm = _grad_norm(model)
        opt.step()

        model.eval()
        with torch.no_grad():
            t_logits = model(x, edge_index)
            acc, base, rec = _link_eval_metrics(t_logits[test_mask], y[test_mask])
            lstats = _logit_stats(t_logits[test_mask])

        print(
            f"  epoch {epoch}: loss={loss.item():.6f} grad_norm={gnorm:.6f} "
            f"test_acc={acc:.4f} baseline={base:.4f} {lstats}",
            flush=True,
        )


def diag_influence(conn, config: TrainConfig) -> None:
    print("\n=== influence_propagation ===", flush=True)
    data, graph = build_user_social_graph(conn)
    edges = load_influence_edges(conn)
    print(f"features: {_feature_stats(data.x)}", flush=True)
    print(f"edges: {data.edge_index.shape[1]}", flush=True)

    node_ids = list(data.node_ids)
    index = {n: i for i, n in enumerate(node_ids)}
    pos_pairs = [(s, t) for s, t in zip(edges["source"], edges["target"]) if s in index and t in index]
    rng = random.Random(config.seed)
    pos_set = set(pos_pairs)
    users = list(index.keys())
    neg_pairs = []
    while len(neg_pairs) < len(pos_pairs):
        s, t = rng.choice(users), rng.choice(users)
        if s != t and (s, t) not in pos_set:
            neg_pairs.append((s, t))

    comm = load_community_map(conn, "layer1")
    split = community_holdout_split(graph, comm, seed=config.seed)
    train_users, test_users = set(split.train_nodes), set(split.test_nodes)
    train_pairs = [(s, t, 1) for s, t in pos_pairs if s in train_users]
    train_pairs += [(s, t, 0) for s, t in neg_pairs if s in train_users]
    test_pairs = _build_balanced_test_pairs(pos_pairs, test_users, users, pos_set, rng, endpoint="either")
    holdout_edges = {(s, t) for s, t, label in test_pairs if label == 1}
    print(f"train_pairs={len(train_pairs)} test_pairs={len(test_pairs)} holdout_edges={len(holdout_edges)}", flush=True)

    model = LinkPredictor(int(data.x.shape[1]), config.hidden)
    opt = optim.Adam(model.parameters(), lr=config.lr)
    x = data.x
    edge_index = _mask_edge_index(data.edge_index, node_ids, holdout_edges)

    for epoch in range(1, config.epochs + 1):
        model.train()
        opt.zero_grad()
        src = torch.tensor([index[s] for s, _, _ in train_pairs], dtype=torch.long)
        dst = torch.tensor([index[t] for _, t, _ in train_pairs], dtype=torch.long)
        y = torch.tensor([float(l) for *_, l in train_pairs], dtype=torch.float)
        logits = model(x, edge_index, src, dst)
        loss = F.binary_cross_entropy_with_logits(logits, y)
        loss.backward()
        gnorm = _grad_norm(model)
        opt.step()

        model.eval()
        with torch.no_grad():
            t_src = torch.tensor([index[s] for s, _, _ in test_pairs], dtype=torch.long)
            t_dst = torch.tensor([index[t] for _, t, _ in test_pairs], dtype=torch.long)
            t_y = torch.tensor([float(l) for *_, l in test_pairs], dtype=torch.float)
            t_logits = model(x, edge_index, t_src, t_dst)
            acc, base, rec = _link_eval_metrics(t_logits, t_y)
            lstats = _logit_stats(t_logits)

        print(
            f"  epoch {epoch}: loss={loss.item():.6f} grad_norm={gnorm:.6f} "
            f"test_acc={acc:.4f} baseline={base:.4f} {lstats}",
            flush=True,
        )


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Log per-epoch training loss on demo DB")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model", choices=("adoption", "churn", "influence", "all"), default="all")
    args = parser.parse_args()
    config = TrainConfig(epochs=args.epochs, seed=args.seed)

    conn = open_db()
    try:
        runners = {
            "adoption": diag_adoption,
            "churn": diag_churn,
            "influence": diag_influence,
        }
        if args.model == "all":
            for fn in runners.values():
                fn(conn, config)
        else:
            runners[args.model](conn, config)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
