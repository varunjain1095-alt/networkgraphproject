# Network Graph Intelligence

A generic network graph intelligence prototype: synthetic data, four graph layers, NetworkX analytics, eight product use cases, and a Plotly Dash dashboard. Phase 2 adds PyG predictions.

**Status:** Project complete — Phase 2 eval/sign-off artifacts (`eval-phase2`, `eval-project`, layer breakdown, overfitting warnings).

## Quick start (full project)

```bash
pip install -r requirements.txt
pip install -r requirements-phase2.txt
python scripts/run.py pipeline-full --scale dev
python scripts/run.py dashboard
```

## Phase 2 setup

```bash
pip install -r requirements-phase2.txt
python scripts/run.py train-models
python scripts/check_influence_recovery.py
python scripts/run.py pre-bugs --phase2 --skip-graphs
python scripts/run.py eval-phase2 --skip-integration
python scripts/run.py eval-project --skip-integration
pytest tests/test_pyg.py tests/test_pyg_training.py tests/test_phase2_pipeline.py -q
```

Predictions are cached to `data/models/predictions.parquet`. The dashboard reads them at startup — no live GNN inference in callbacks.

For demo-scale (~10k users), use `--scale demo` on `pipeline-full` (expect ~30+ minutes for generate + graph build).

## Quick start (demo)

```bash
# 1. Create virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# 2. Install Phase 1 dependencies
pip install -r requirements.txt

# 3. Copy environment file
copy .env.example .env          # Windows
# cp .env.example .env          # macOS/Linux

# 4. Validate config
python scripts/check_env.py

# 5. One-command demo (dev scale ~500 users, ~2 min)
python scripts/run.py demo

# 6. Open dashboard
python scripts/run.py dashboard
# → http://127.0.0.1:8050
```

Use `--scale dev` for fast iteration (~500 users). Use `--scale medium` for richer networks (~2,500 users). Use `--scale demo` for the full ~10k-user dataset.

### Scale and runtime expectations

| Scale | Users | Generate + graphs | Metrics compute | Best for |
|---|---|---|---|---|
| `dev` | ~500 | ~2 min | ~3–5 min | Fast iteration, tests |
| `medium` | ~2,500 | ~8–15 min | ~20–60 min | Rich layers without demo wait |
| `demo` | ~10,000 | ~25–40 min | **2–4+ hours** | Full presentation dataset |

**Important:** `pre-bugs` recomputes metrics from scratch unless you pass `--skip-metrics` (when cache is fresh). For visual testing after a successful pipeline, run `python scripts/run.py dashboard` directly — do not run full pre-bugs first on demo scale.

## Pipeline commands

| Command | Phase | Description |
|---|---|---|
| `demo` | 1F | Dev pipeline + instructions to start dashboard |
| `pipeline` | 1F | generate → validate → graphs → metrics |
| `pipeline-full` | 2 | Phase 1 pipeline + train-models + recovery check |
| `train-models` | 2 | Train PyG models and cache predictions |
| `generate` | 1A | Synthetic data generation |
| `validate` | 1A | Data validation |
| `graphs` | 1B | Build four graph layers |
| `metrics` | 1C | Compute NetworkX metrics |
| `use-cases` | 1D | Run all use case modules |
| `dashboard` | 1E | Start Plotly Dash app |
| `check-cache` | 1F | Verify graph/metrics cache is newer than DB |
| `perf-smoke` | 1F/1G | Dashboard data load < 5 seconds |
| `pre-bugs` | 1G | Full automated checklist before visual testing |
| `eval-phase1` | 1 | Phase 1 automated eval gate |
| `eval-phase2` | 2 | Phase 2 automated eval gate |
| `eval-project` | 2 | Full project sign-off (Phase 1 + Phase 2) |

Cross-platform CLI:

```bash
python scripts/run.py help
python scripts/run.py demo --scale dev --seed 42
python scripts/run.py pipeline --scale dev
python scripts/run.py dashboard
python scripts/run.py pre-bugs --skip-graphs   # before opening browser
```

With Make (if installed):

```bash
make demo
make dashboard
make pre-bugs
make check-cache
make test
make test-integration
```

### Pre-bugs checklist (Phase 1G)

Run before manual dashboard spot-checks from `evals.md`:

```bash
python scripts/run.py pre-bugs              # full runbook (includes graph rebuild)
python scripts/run.py pre-bugs --skip-graphs  # faster if cache is already fresh
```

Individual checks:

```bash
python validator/run_validation.py --all
python scripts/check_cache_freshness.py
python scripts/audit_feature_columns.py
python scripts/perf_smoke.py
python scripts/check_env.py --check-git
pytest tests/ -q
```

### Manual step-by-step

```bash
python generator/run_generator.py --scale dev --seed 42 --force-schema
python validator/run_validation.py --all
python graphs/builder.py --all-layers --clear-cache
python analytics/networkx_metrics.py
python dashboard/app.py
```

## Troubleshooting

- **Startup banner / missing graphs:** Run `python scripts/run.py pipeline --scale dev` first.
- **Stale rankings after regenerate:** Run `python scripts/run.py check-cache`. Rebuild graphs and metrics if stale.
- **SQLite lock errors:** Stop the dashboard before regenerating data (`Ctrl+C` on the dashboard process).
- **Slow demo:** Default `demo` uses `--scale dev`. Demo scale (`--scale demo`) is for presentations only.

Phase 2 PyG dependencies are separate:

```bash
pip install -r requirements-phase2.txt
```

## Project layout

```
config/          Environment and domain config loaders
schema/          SQLite DDL
scripts/         CLI utilities (check_env, run, pipeline, perf_smoke)
generator/       Synthetic data (Phase 1A)
validator/       Data validation (Phase 1A)
graphs/          Graph builder (Phase 1B)
analytics/       NetworkX + PyG (Phase 1C / Phase 2)
use_cases/       Eight use case modules (Phase 1D)
dashboard/       Plotly Dash UI (Phase 1E)
tests/           Pytest suite (unit + integration)
data/            Generated data (gitignored)
```

## Configuration

- **`domain_config.yaml`** — entity name mappings (gaming vs SaaS examples)
- **`.env`** — local paths, generator seed, dashboard port (no API keys)

See `context.md`, `architecture.md`, and `implementation.md` for full build plan.

## Tests

```bash
pytest tests/ -m "not integration" -q   # unit tests (fast)
pytest tests/ -m integration -q         # end-to-end pipeline (slower)
pytest tests/ -q                        # all tests
```

## Docs

| File | Purpose |
|---|---|
| `context.md` | Product concept and use cases |
| `architecture.md` | System design and folder structure |
| `implementation.md` | Phase-by-phase build guide |
| `dataschema.md` | SQLite column-level schema |
| `bugs.md` | Pre-visual testing checklist |
| `evals.md` | Phase pass/fail criteria |
