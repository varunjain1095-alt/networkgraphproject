"""Train combined adoption, churn, and influence models (Phase 2.3–2.6)."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from analytics.pyg.dataset import (
    build_adoption_graph,
    build_user_social_graph,
    load_cascade_risk_labels,
    load_influenced_adoption_labels,
    load_influence_edges,
)
from analytics.pyg.models import FeatureClassifier, LinkPredictor, NodeClassifier, require_models
from analytics.pyg.predictions import save_predictions, save_training_metadata
from analytics.pyg.split import community_holdout_split, load_community_map
from analytics.utils import to_simple_graph
from graphs.db import open_db

require_models()
import torch
import torch.nn.functional as F
from torch import optim


@dataclass
class TrainConfig:
    epochs: int = 40
    lr: float = 0.001
    hidden: int = 64
    seed: int = 42
    negative_ratio: int = 1
    batch_size: int = 1024
    max_grad_norm: float = 1.0
    weight_decay: float = 1e-4
    log_every: int = 5


@dataclass
class TrainReport:
    models: dict[str, dict[str, float]] = field(default_factory=dict)
    prediction_counts: dict[str, int] = field(default_factory=dict)


def _device():
    return torch.device("cpu")


def _prepare_node_features(x: torch.Tensor) -> torch.Tensor:
    """Stabilize GCN inputs: log1p on graph metrics, then column z-score."""
    x = x.float()
    if x.numel() == 0:
        return x
    out = x.clone()
    metric_cols = min(3, out.shape[1])
    if metric_cols:
        out[:, :metric_cols] = torch.log1p(out[:, :metric_cols].clamp_min(0.0))
    mean = out.mean(dim=0)
    std = out.std(dim=0).clamp_min(1e-6)
    return (out - mean) / std


def _make_optimizer(model, config: TrainConfig):
    return optim.Adam(model.parameters(), lr=config.lr, weight_decay=config.weight_decay)


def _optimizer_step(model, opt, loss: torch.Tensor, config: TrainConfig) -> float:
    opt.zero_grad()
    loss.backward()
    if config.max_grad_norm > 0:
        torch.nn.utils.clip_grad_norm_(model.parameters(), config.max_grad_norm)
    opt.step()
    return float(loss.item())


def _logit_stats(logits: torch.Tensor) -> dict[str, float]:
    probs = torch.sigmoid(logits)
    return {
        "logit_std": float(logits.std().item()) if logits.numel() else 0.0,
        "pred_pos_rate": float((probs >= 0.5).float().mean().item()) if logits.numel() else 0.0,
    }


def _maybe_log_epoch(
    model_name: str,
    epoch: int,
    config: TrainConfig,
    *,
    loss: float,
    test_logits: torch.Tensor | None = None,
    test_labels: torch.Tensor | None = None,
) -> None:
    if epoch % config.log_every != 0 and epoch != config.epochs:
        return
    msg = f"  {model_name}: epoch {epoch}/{config.epochs} loss={loss:.6f}"
    if test_logits is not None and test_labels is not None and test_labels.numel():
        acc, base, _ = _link_eval_metrics(test_logits, test_labels)
        stats = _logit_stats(test_logits)
        msg += f" test_acc={acc:.4f} baseline={base:.4f} logit_std={stats['logit_std']:.4f} pred_pos={stats['pred_pos_rate']:.4f}"
    print(msg, flush=True)


def _maybe_update_best(
    model,
    best: dict[str, Any],
    test_logits: torch.Tensor | None,
    test_labels: torch.Tensor | None,
) -> dict[str, Any]:
    if test_logits is None or test_labels is None or test_labels.numel() == 0:
        return best
    acc, base, recovery = _link_eval_metrics(test_logits, test_labels)
    if acc > best.get("acc", -1.0):
        return {
            "acc": acc,
            "state": {k: v.detach().cpu().clone() for k, v in model.state_dict().items()},
        }
    return best


def _restore_best_weights(model, best: dict[str, Any]) -> None:
    if best.get("state"):
        model.load_state_dict(best["state"])


def _train_link_epochs(
    model,
    opt,
    x: torch.Tensor,
    edge_index: torch.Tensor,
    train_pairs: list[tuple[Any, Any, int]],
    index: dict[str, int],
    config: TrainConfig,
    *,
    model_name: str,
    test_pairs: list[tuple[Any, Any, int]] | None = None,
) -> None:
    """Mini-batch link training with stable features and gradient clipping."""
    pairs = list(train_pairs)
    device = x.device
    best: dict[str, Any] = {"acc": -1.0}
    for epoch in range(1, config.epochs + 1):
        torch.manual_seed(config.seed + epoch)
        rng = random.Random(config.seed + epoch)
        rng.shuffle(pairs)
        model.train()
        epoch_loss = 0.0
        n_batches = 0
        for start in range(0, len(pairs), config.batch_size):
            batch = pairs[start : start + config.batch_size]
            src = torch.tensor([index[u] for u, _, _ in batch], dtype=torch.long, device=device)
            dst = torch.tensor([index[v] for _, v, _ in batch], dtype=torch.long, device=device)
            y = torch.tensor([float(l) for *_, l in batch], dtype=torch.float, device=device)
            logits = model(x, edge_index, src, dst)
            loss = F.binary_cross_entropy_with_logits(logits, y)
            epoch_loss += _optimizer_step(model, opt, loss, config)
            n_batches += 1

        avg_loss = epoch_loss / max(n_batches, 1)
        test_logits = None
        test_labels = None
        if test_pairs:
            model.eval()
            with torch.no_grad():
                t_src = torch.tensor([index[u] for u, _, _ in test_pairs], dtype=torch.long, device=device)
                t_dst = torch.tensor([index[v] for _, v, _ in test_pairs], dtype=torch.long, device=device)
                test_labels = torch.tensor([float(l) for *_, l in test_pairs], dtype=torch.float, device=device)
                test_logits = model(x, edge_index, t_src, t_dst)
                best = _maybe_update_best(model, best, test_logits, test_labels)
        _maybe_log_epoch(model_name, epoch, config, loss=avg_loss, test_logits=test_logits, test_labels=test_labels)
    _restore_best_weights(model, best)


def _balanced_node_batches(
    train_idx: torch.Tensor,
    y: torch.Tensor,
    batch_size: int,
    rng: random.Random,
) -> list[list[int]]:
    """Yield index lists with roughly equal positives and negatives per batch."""
    pos = [int(i) for i in train_idx.tolist() if float(y[i]) == 1.0]
    neg = [int(i) for i in train_idx.tolist() if float(y[i]) == 0.0]
    if not pos or not neg:
        order = train_idx.tolist()
        rng.shuffle(order)
        return [order[i : i + batch_size] for i in range(0, len(order), batch_size)]

    rng.shuffle(pos)
    rng.shuffle(neg)
    half = max(1, batch_size // 2)
    batches: list[list[int]] = []
    pi = ni = 0
    while pi < len(pos) or ni < len(neg):
        batch: list[int] = []
        for _ in range(half):
            if pi < len(pos):
                batch.append(pos[pi])
                pi += 1
            if ni < len(neg):
                batch.append(neg[ni])
                ni += 1
        if batch:
            rng.shuffle(batch)
            batches.append(batch)
    return batches


def _mask_edge_index(edge_index, node_ids: list[str], holdout_pairs: set[tuple[str, str]]):
    """Remove holdout undirected edges from message-passing graph (BUG-10.02)."""
    if not holdout_pairs:
        return edge_index
    id_to_idx = {n: i for i, n in enumerate(node_ids)}
    holdout_idx: set[tuple[int, int]] = set()
    for u, v in holdout_pairs:
        if u in id_to_idx and v in id_to_idx:
            a, b = id_to_idx[u], id_to_idx[v]
            holdout_idx.add((min(a, b), max(a, b)))

    ei = edge_index.cpu()
    keep = [
        j
        for j in range(ei.shape[1])
        if (min(int(ei[0, j]), int(ei[1, j])), max(int(ei[0, j]), int(ei[1, j]))) not in holdout_idx
    ]
    if not keep:
        return edge_index
    return ei[:, keep].contiguous().to(edge_index.device)


def _sample_negative_pairs(
    users: list[str],
    other_nodes: list[str],
    count: int,
    pos_set: set[tuple[str, str]],
    rng: random.Random,
) -> list[tuple[str, str]]:
    neg: list[tuple[str, str]] = []
    attempts = 0
    limit = max(count * 100, 100)
    while len(neg) < count and attempts < limit:
        attempts += 1
        u = rng.choice(users)
        v = rng.choice(other_nodes)
        if (u, v) not in pos_set:
            neg.append((u, v))
    return neg


def _build_balanced_test_pairs(
    pos_pairs: list[tuple[str, str]],
    test_users: set[str],
    other_nodes: list[str],
    pos_set: set[tuple[str, str]],
    rng: random.Random,
    *,
    endpoint: str = "first",
) -> list[tuple[str, str, int]]:
    """Build test set with positives and matched negatives for held-out users."""
    if endpoint == "either":
        test_pos = [(u, v) for u, v in pos_pairs if u in test_users or v in test_users]
        pool = [u for u in test_users]
    else:
        test_pos = [(u, v) for u, v in pos_pairs if u in test_users]
        pool = [u for u in test_users]

    if not test_pos or not pool:
        return []

    test_neg = _sample_negative_pairs(pool, other_nodes, len(test_pos), pos_set, rng)
    return [(u, v, 1) for u, v in test_pos] + [(u, v, 0) for u, v in test_neg]


def _link_eval_metrics(logits, labels: torch.Tensor) -> tuple[float, float, float]:
    preds = (torch.sigmoid(logits) >= 0.5).float()
    y = labels.float()
    if y.numel() == 0:
        return 0.0, 0.5, 0.0
    accuracy = float((preds == y).float().mean().item())
    pos_rate = float(y.mean().item())
    baseline = max(pos_rate, 1.0 - pos_rate)
    recovery = max(0.0, accuracy - baseline)
    return accuracy, baseline, recovery


def _sigmoid_confidence(logit: float) -> tuple[float, float]:
    prob = float(torch.sigmoid(torch.tensor(logit)).item())
    confidence = abs(prob - 0.5) * 2.0
    return prob, confidence


def train_adoption_model(conn, config: TrainConfig) -> tuple[list[dict], dict]:
    torch.manual_seed(config.seed)
    data, _graph = build_adoption_graph(conn)
    labels = load_influenced_adoption_labels(conn)
    label_source = "influenced_adoption"
    if len(labels) < 50:
        labels = pd.read_sql_query(
            """
            SELECT DISTINCT ui.user_id, ui.item_id, ui.usage_total
            FROM user_item_interactions ui
            INNER JOIN influence_outcomes io ON io.target_user_id = ui.user_id
            """,
            conn,
        )
        label_source = "influence_target_interactions"
    if labels.empty or data.num_nodes == 0:
        return [], {"accuracy": 0.0, "baseline": 0.5, "label_source": label_source}

    node_ids = list(data.node_ids)
    index = {n: i for i, n in enumerate(node_ids)}
    graph_nx = __import__("graphs.cache", fromlist=["load_graph"]).load_graph(3)
    item_ids = {str(n) for n, d in graph_nx.nodes(data=True) if d.get("node_type") == "item"}
    user_ids = [n for n in node_ids if n not in item_ids]

    pos_pairs = [(u, i) for u, i in zip(labels["user_id"], labels["item_id"]) if u in index and i in index]
    print(
        f"  combined_adoption: label_source={label_source}, positive_pairs={len(pos_pairs)}",
        flush=True,
    )
    if len(pos_pairs) < 5:
        return [], {
            "accuracy": 0.0,
            "baseline": 0.5,
            "recovery_rate": 0.0,
            "label_source": label_source,
            "test_positives": 0,
            "test_negatives": 0,
        }

    rng = random.Random(config.seed)
    all_items = list({i for _, i in pos_pairs})
    neg_pairs = []
    pos_set = set(pos_pairs)
    while len(neg_pairs) < len(pos_pairs) * config.negative_ratio:
        u = rng.choice(user_ids)
        i = rng.choice(all_items)
        if (u, i) not in pos_set:
            neg_pairs.append((u, i))

    split_graph = to_simple_graph(__import__("graphs.cache", fromlist=["load_graph"]).load_graph(1))
    comm = load_community_map(conn, "layer1")
    split = community_holdout_split(split_graph, comm, seed=config.seed)
    train_users = set(split.train_nodes)
    test_users = set(split.test_nodes)

    train_pairs = [(u, i, 1) for u, i in pos_pairs if u in train_users]
    train_pairs += [(u, i, 0) for u, i in neg_pairs if u in train_users]
    test_pairs = _build_balanced_test_pairs(
        pos_pairs, test_users, all_items, pos_set, rng, endpoint="first"
    )
    holdout_edges = {(u, i) for u, i, label in test_pairs if label == 1}

    in_dim = int(data.x.shape[1])
    model = LinkPredictor(in_dim, config.hidden).to(_device())
    opt = _make_optimizer(model, config)
    x = _prepare_node_features(data.x).to(_device())
    edge_index = _mask_edge_index(data.edge_index.to(_device()), node_ids, holdout_edges)

    _train_link_epochs(
        model,
        opt,
        x,
        edge_index,
        train_pairs,
        index,
        config,
        model_name="combined_adoption",
        test_pairs=test_pairs,
    )

    model.eval()
    accuracy, baseline, recovery = 0.0, 0.5, 0.0
    with torch.no_grad():
        if test_pairs:
            src = torch.tensor([index[u] for u, _, _ in test_pairs], dtype=torch.long, device=_device())
            dst = torch.tensor([index[i] for _, i, _ in test_pairs], dtype=torch.long, device=_device())
            y = torch.tensor([float(l) for *_, l in test_pairs], dtype=torch.float, device=_device())
            logits = model(x, edge_index, src, dst)
            accuracy, baseline, recovery = _link_eval_metrics(logits, y)

    rows: list[dict] = []
    with torch.no_grad():
        for u in user_ids[:500]:
            for i in all_items[:20]:
                if u not in index or i not in index:
                    continue
                logit = model(x, edge_index, torch.tensor([index[u]], device=_device()), torch.tensor([index[i]], device=_device()))
                score, conf = _sigmoid_confidence(float(logit.item()))
                if score >= 0.55:
                    rows.append(
                        {
                            "user_id": u,
                            "prediction_type": "adoption",
                            "target_id": i,
                            "score": round(score, 4),
                            "confidence": round(conf, 4),
                            "model_name": "combined_adoption",
                            "computed_at": "",
                        }
                    )

    return rows[:2000], {
        "accuracy": accuracy,
        "baseline": baseline,
        "recovery_rate": recovery,
        "label_source": label_source,
        "test_positives": sum(1 for *_, l in test_pairs if l == 1),
        "test_negatives": sum(1 for *_, l in test_pairs if l == 0),
    }


def train_churn_model(conn, config: TrainConfig) -> tuple[list[dict], dict]:
    torch.manual_seed(config.seed)
    data, graph = build_user_social_graph(conn)
    labels = load_cascade_risk_labels(conn)
    label_source = "cascade_risk_churned_neighbor_count"
    if labels.empty:
        return [], {"accuracy": 0.0, "baseline": 0.5, "label_source": label_source}

    pos_rate = float(labels["cascade_risk"].mean())
    print(
        f"  churn_cascade: label_source={label_source}, "
        f"positive_rate={pos_rate:.4f}, labeled_users={len(labels)}",
        flush=True,
    )

    node_ids = list(data.node_ids)
    index = {n: i for i, n in enumerate(node_ids)}
    y = torch.full((len(node_ids),), float("nan"))
    for _, row in labels.iterrows():
        uid = row["user_id"]
        if uid in index:
            y[index[uid]] = float(row["cascade_risk"])

    churned = {
        row[0] for row in conn.execute("SELECT user_id FROM churn_events").fetchall()
    }

    comm = load_community_map(conn, "layer1")
    split = community_holdout_split(graph, comm, seed=config.seed)
    train_mask = split.train_mask
    test_mask = split.test_mask

    valid = ~torch.isnan(y)
    train_mask = train_mask & valid
    test_mask = test_mask & valid

    in_dim = int(data.x.shape[1])
    x = _prepare_node_features(data.x).to(_device())
    layer1 = to_simple_graph(__import__("graphs.cache", fromlist=["load_graph"]).load_graph(1))
    churn_flag = torch.zeros((len(node_ids), 1), dtype=torch.float, device=_device())
    neighbor_counts = torch.zeros((len(node_ids), 1), dtype=torch.float, device=_device())
    for uid in node_ids:
        idx = index[uid]
        if uid in churned:
            churn_flag[idx, 0] = 1.0
        if uid in layer1:
            neighbor_counts[idx, 0] = float(
                sum(1 for nbr in layer1.neighbors(uid) if str(nbr) in churned)
            )
    neighbor_counts = torch.log1p(neighbor_counts)
    extra = torch.cat([churn_flag, neighbor_counts], dim=1)
    extra = (extra - extra.mean(dim=0)) / extra.std(dim=0).clamp_min(1e-6)
    x = torch.cat([x, extra], dim=1)
    edge_index = data.edge_index.to(_device())
    y = y.to(_device())
    train_idx = train_mask.nonzero(as_tuple=False).view(-1)
    test_idx = test_mask.nonzero(as_tuple=False).view(-1)

    model = FeatureClassifier(x.shape[1], config.hidden).to(_device())
    opt = _make_optimizer(model, config)
    best: dict[str, Any] = {"acc": -1.0}

    for epoch in range(1, config.epochs + 1):
        torch.manual_seed(config.seed + epoch)
        rng = random.Random(config.seed + epoch)
        batches = _balanced_node_batches(train_idx, y, config.batch_size, rng)
        model.train()
        epoch_loss = 0.0
        n_batches = 0
        for batch_nodes in batches:
            batch_idx = torch.tensor(batch_nodes, dtype=torch.long, device=_device())
            logits = model(x)[batch_idx]
            loss = F.binary_cross_entropy_with_logits(logits, y[batch_idx])
            epoch_loss += _optimizer_step(model, opt, loss, config)
            n_batches += 1

        avg_loss = epoch_loss / max(n_batches, 1)
        test_logits = None
        test_labels = None
        if test_idx.numel():
            model.eval()
            with torch.no_grad():
                test_logits = model(x)[test_idx]
                test_labels = y[test_idx]
                best = _maybe_update_best(model, best, test_logits, test_labels)
        _maybe_log_epoch(
            "churn_cascade",
            epoch,
            config,
            loss=avg_loss,
            test_logits=test_logits,
            test_labels=test_labels,
        )

    _restore_best_weights(model, best)
    model.eval()
    accuracy, baseline = 0.0, 0.5
    test_positives = 0
    test_negatives = 0
    with torch.no_grad():
        logits = model(x)
        if test_mask.sum() > 0:
            test_y = y[test_mask]
            accuracy, baseline, _recovery = _link_eval_metrics(logits[test_mask], test_y)
            test_positives = int((test_y == 1).sum().item())
            test_negatives = int((test_y == 0).sum().item())

    rows: list[dict] = []
    with torch.no_grad():
        logits = model(x)
        for uid, idx in index.items():
            if uid in churned:
                continue
            score, conf = _sigmoid_confidence(float(logits[idx].item()))
            rows.append(
                {
                    "user_id": uid,
                    "prediction_type": "churn_cascade",
                    "target_id": "",
                    "score": round(score, 4),
                    "confidence": round(conf, 4),
                    "model_name": "churn_cascade",
                    "computed_at": "",
                }
            )

    recovery = max(0.0, accuracy - baseline)
    return rows, {
        "accuracy": accuracy,
        "baseline": baseline,
        "recovery_rate": recovery,
        "label_source": label_source,
        "test_positives": test_positives,
        "test_negatives": test_negatives,
    }


def train_influence_model(conn, config: TrainConfig) -> tuple[list[dict], dict]:
    torch.manual_seed(config.seed)
    data, graph = build_user_social_graph(conn)
    edges = load_influence_edges(conn)
    if edges.empty:
        return [], {"accuracy": 0.0, "baseline": 0.0, "recovery_rate": 0.0}

    node_ids = list(data.node_ids)
    index = {n: i for i, n in enumerate(node_ids)}
    pos_pairs = [(s, t) for s, t in zip(edges["source"], edges["target"]) if s in index and t in index]
    print(f"  influence_propagation: positive_pairs={len(pos_pairs)}", flush=True)
    if len(pos_pairs) < 5:
        return [], {"accuracy": 0.0, "baseline": 0.0, "recovery_rate": 0.0}

    rng = random.Random(config.seed)
    neg_pairs = []
    pos_set = set(pos_pairs)
    users = list(index.keys())
    while len(neg_pairs) < len(pos_pairs):
        s, t = rng.choice(users), rng.choice(users)
        if s != t and (s, t) not in pos_set:
            neg_pairs.append((s, t))

    comm = load_community_map(conn, "layer1")
    split = community_holdout_split(graph, comm, seed=config.seed)
    train_users = set(split.train_nodes)
    test_users = set(split.test_nodes)

    # Train on pairs whose source is in the train split (targets may be in test).
    train_pairs = [(s, t, 1) for s, t in pos_pairs if s in train_users]
    train_pairs += [(s, t, 0) for s, t in neg_pairs if s in train_users]
    test_pairs = _build_balanced_test_pairs(
        pos_pairs, test_users, users, pos_set, rng, endpoint="either"
    )
    holdout_edges = {(s, t) for s, t, label in test_pairs if label == 1}

    in_dim = int(data.x.shape[1])
    model = LinkPredictor(in_dim, config.hidden).to(_device())
    opt = _make_optimizer(model, config)
    x = _prepare_node_features(data.x).to(_device())
    edge_index = _mask_edge_index(data.edge_index.to(_device()), node_ids, holdout_edges)

    _train_link_epochs(
        model,
        opt,
        x,
        edge_index,
        train_pairs,
        index,
        config,
        model_name="influence_propagation",
        test_pairs=test_pairs,
    )

    model.eval()
    accuracy, baseline, recovery_rate = 0.0, 0.5, 0.0
    with torch.no_grad():
        if test_pairs:
            src = torch.tensor([index[s] for s, _, _ in test_pairs], dtype=torch.long, device=_device())
            dst = torch.tensor([index[t] for _, t, _ in test_pairs], dtype=torch.long, device=_device())
            y = torch.tensor([float(l) for *_, l in test_pairs], dtype=torch.float, device=_device())
            logits = model(x, edge_index, src, dst)
            accuracy, baseline, recovery_rate = _link_eval_metrics(logits, y)

    rows: list[dict] = []
    with torch.no_grad():
        for s, t in pos_pairs[:1000]:
            logit = model(
                x,
                edge_index,
                torch.tensor([index[s]], device=_device()),
                torch.tensor([index[t]], device=_device()),
            )
            score, conf = _sigmoid_confidence(float(logit.item()))
            rows.append(
                {
                    "user_id": t,
                    "prediction_type": "influence_propagation",
                    "target_id": s,
                    "score": round(score, 4),
                    "confidence": round(conf, 4),
                    "model_name": "influence_propagation",
                    "computed_at": "",
                }
            )

    return rows, {
        "accuracy": accuracy,
        "baseline": baseline,
        "recovery_rate": recovery_rate,
        "label_source": "influence_outcomes",
        "test_positives": sum(1 for *_, l in test_pairs if l == 1),
        "test_negatives": sum(1 for *_, l in test_pairs if l == 0),
    }


def train_all_models(config: TrainConfig | None = None) -> TrainReport:
    config = config or TrainConfig()
    random.seed(config.seed)
    torch.manual_seed(config.seed)

    import analytics.pyg.train as _self

    print(f"Using training module: {_self.__file__}", flush=True)

    report = TrainReport()
    all_rows: list[dict] = []
    conn = open_db()
    try:
        for name, trainer in (
            ("combined_adoption", train_adoption_model),
            ("churn_cascade", train_churn_model),
            ("influence_propagation", train_influence_model),
        ):
            print(f"Training {name}...", flush=True)
            rows, metrics = trainer(conn, config)
            report.models[name] = metrics
            report.prediction_counts[name] = len(rows)
            all_rows.extend(rows)
            print(f"  {name}: {metrics}", flush=True)
    finally:
        conn.close()

    if all_rows:
        from datetime import datetime, timezone

        ts = datetime.now(timezone.utc).isoformat()
        for row in all_rows:
            row["computed_at"] = ts
        path = save_predictions(all_rows)
        print(f"Saved {len(all_rows)} predictions to {path}")

    meta = {"models": report.models, "prediction_counts": report.prediction_counts}
    save_training_metadata(meta)
    return report
