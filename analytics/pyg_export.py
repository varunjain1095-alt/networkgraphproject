"""Export NetworkX graphs to PyG Data objects (Phase 2.1)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.env import load_env
from analytics.pyg.convert import export_all_layers, require_pyg


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Export cached graphs to PyG format")
    parser.add_argument("--all-layers", action="store_true", help="Export layers 1-4")
    args = parser.parse_args()

    if not args.all_layers:
        parser.print_help()
        return 1

    try:
        require_pyg()
        export_all_layers()
        return 0
    except ImportError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"PyG export FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
