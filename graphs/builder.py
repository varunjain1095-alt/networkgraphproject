"""Build all graph layers from SQLite and cache to disk."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.env import load_env, resolve_path
from graphs.cache import clear_cache, save_graphs
from graphs.db import open_db
from graphs.layers import build_layer1, build_layer2, build_layer3, build_layer4
from graphs.projections import build_projections


def build_all_layers(db_path: Path | None = None, rebuild_cache: bool = True) -> dict:
    conn = open_db(db_path)
    try:
        t0 = time.time()
        print("Building Layer 1 (relationships)...", flush=True)
        layer1 = build_layer1(conn)
        print("Building Layer 2 (shared activity)...", flush=True)
        layer2 = build_layer2(conn)
        print("Building Layer 3 (user-item)...", flush=True)
        layer3 = build_layer3(conn)
        print("Building Layer 4 (influence)...", flush=True)
        layer4 = build_layer4(conn)
        print("Building projections...", flush=True)
        projections = build_projections(conn)

        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        layers = {"layer1": layer1, "layer2": layer2, "layer3": layer3, "layer4": layer4}
        metadata = {
            "user_count": user_count,
            "layer1_nodes": layer1.number_of_nodes(),
            "layer1_edges": layer1.number_of_edges(),
            "layer2_nodes": layer2.number_of_nodes(),
            "layer2_edges": layer2.number_of_edges(),
            "layer3_nodes": layer3.number_of_nodes(),
            "layer3_edges": layer3.number_of_edges(),
            "layer4_nodes": layer4.number_of_nodes(),
            "layer4_edges": layer4.number_of_edges(),
            "item_item_edges": projections["item_item"].number_of_edges(),
            "user_user_edges": projections["user_user"].number_of_edges(),
            "build_seconds": round(time.time() - t0, 2),
        }

        if rebuild_cache:
            if db_path is None:
                db_path = resolve_path("DATABASE_PATH", "data/synthetic.db")
            metadata["database_path"] = str(db_path)
            metadata["database_mtime"] = db_path.stat().st_mtime
            save_graphs(layers, projections, metadata)

        _print_summary(metadata)
        return {"layers": layers, "projections": projections, "metadata": metadata}
    finally:
        conn.close()


def _print_summary(meta: dict) -> None:
    print("\nGraph build summary:")
    print(f"  Layer 1: {meta['layer1_nodes']:,} nodes, {meta['layer1_edges']:,} edges")
    print(f"  Layer 2: {meta['layer2_nodes']:,} nodes, {meta['layer2_edges']:,} edges")
    print(f"  Layer 3: {meta['layer3_nodes']:,} nodes, {meta['layer3_edges']:,} edges")
    print(f"  Layer 4: {meta['layer4_nodes']:,} nodes, {meta['layer4_edges']:,} edges")
    print(f"  Projections: {meta['item_item_edges']:,} item-item, {meta['user_user_edges']:,} user-user")
    print(f"  Build time: {meta['build_seconds']}s")


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Build graph layers from SQLite")
    parser.add_argument("--all-layers", action="store_true", help="Build all layers and cache")
    parser.add_argument("--clear-cache", action="store_true", help="Clear graph cache before build")
    args = parser.parse_args()

    if args.clear_cache:
        clear_cache()

    try:
        build_all_layers(rebuild_cache=True)
        return 0
    except Exception as exc:
        print(f"Graph build FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
