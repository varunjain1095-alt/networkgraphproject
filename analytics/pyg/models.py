"""Lightweight GNN modules for Phase 2."""

from __future__ import annotations

try:
    import torch
    import torch.nn.functional as F
    from torch import nn
    from torch_geometric.nn import GCNConv

    HAS_PYG = True
except ImportError:
    HAS_PYG = False


def require_models() -> None:
    if not HAS_PYG:
        raise ImportError("PyTorch and torch-geometric required")


class GCNEncoder(nn.Module):
    def __init__(self, in_channels: int, hidden: int = 32, out_channels: int = 16):
        super().__init__()
        self.conv1 = GCNConv(in_channels, hidden)
        self.conv2 = GCNConv(hidden, out_channels)

    def forward(self, x, edge_index):
        x = self.conv1(x, edge_index)
        x = F.relu(x)
        x = F.dropout(x, p=0.1, training=self.training)
        return self.conv2(x, edge_index)


class NodeClassifier(nn.Module):
    def __init__(self, in_channels: int, hidden: int = 32, *, skip_raw: bool = False):
        super().__init__()
        self.skip_raw = skip_raw
        self.encoder = GCNEncoder(in_channels, hidden, hidden)
        head_in = hidden + (in_channels if skip_raw else 0)
        self.head = nn.Linear(head_in, 1)

    def forward(self, x, edge_index):
        z = self.encoder(x, edge_index)
        if self.skip_raw:
            z = torch.cat([z, x], dim=-1)
        return self.head(z).squeeze(-1)


class FeatureClassifier(nn.Module):
    """Tabular classifier for tasks with explicit node-level risk features."""

    def __init__(self, in_channels: int, hidden: int = 32):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_channels, hidden),
            nn.ReLU(),
            nn.Linear(hidden, 1),
        )

    def forward(self, x, edge_index=None):
        return self.net(x).squeeze(-1)


class LinkPredictor(nn.Module):
    """Dot-product decoder for user-item or user-user links."""

    def __init__(self, in_channels: int, hidden: int = 32):
        super().__init__()
        self.encoder = GCNEncoder(in_channels, hidden, hidden)

    def encode(self, x, edge_index):
        return self.encoder(x, edge_index)

    def decode(self, z, src_idx, dst_idx):
        z_src = F.normalize(z[src_idx], p=2, dim=-1)
        z_dst = F.normalize(z[dst_idx], p=2, dim=-1)
        return (z_src * z_dst).sum(dim=-1)

    def forward(self, x, edge_index, src_idx, dst_idx):
        z = self.encode(x, edge_index)
        return self.decode(z, src_idx, dst_idx)
