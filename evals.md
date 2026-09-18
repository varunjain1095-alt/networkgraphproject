# Evals — Network Graph Intelligence Project

This document defines how we verify each phase works, what counts as pass or fail, and what success looks like.

Each phase includes:
- **What we're checking**
- **Why this eval matters** (plain English)
- **Why you should care**
- **How to run it**
- **Pass criteria**
- **Fail criteria**
- **What success looks like**

Use this as the gate before moving to the next phase. Do not skip evals — a phase that "seems done" but fails its eval will cause silent problems downstream.

---

## How evals work in this project

We use three types of checks:

| Type | What it is | When to use |
|---|---|---|
| **Automated** | Script or test that returns pass/fail | Every phase — run in CI or before commits |
| **Validation report** | Structured output with counts, distributions, and check results | After data generation, graph build, metric compute |
| **Manual spot-check** | A human opens the dashboard and clicks through a short checklist | After dashboard and integration phases |

**In plain English:** Automated checks catch obvious breaks. Validation reports catch "technically works but data is wrong." Manual spot-checks catch "works in code but confusing for a PM."

---

## Phase 0 — Project setup

### What we're checking
The empty project installs, loads config, creates a database shell, and can be invoked with simple run commands.

### Why this eval matters
If setup is flaky, every later phase wastes time on environment issues instead of building features.

### Why you should care
You should be one command away from "generate data" or "open dashboard." If setup takes 30 minutes every time, development slows to a crawl.

### How to run it

```bash
pip install -r requirements.txt
python -c "import yaml; yaml.safe_load(open('domain_config.yaml'))"
python scripts/check_env.py
python scripts/init_db.py          # or equivalent
make help                          # or scripts listed in README
```

### Pass criteria

| Check | Pass |
|---|---|
| Dependencies install without error | Yes |
| `domain_config.yaml` loads and returns entity mappings | Yes |
| `.env.example` present; `.env` gitignored | Yes |
| `config/env.py` loads `DATABASE_PATH` from `.env` | Yes |
| `check_env.py` passes | Yes |
| Empty SQLite DB created with all table shells | Yes |
| Folder structure matches architecture.md | Yes |
| Run scripts documented (`generate`, `validate`, `dashboard`) | Yes |
| Phase 2 deps NOT required for Phase 0/1 install | Yes |
| `.env` not tracked by git | Yes |

### Fail criteria

- Import errors on core packages
- Config file missing or malformed
- `.env` variables not loading
- Database creation fails
- No documented way to run the pipeline
- `.env` committed to repository

### What success looks like
A new developer clones the repo, runs install + init, and gets a clean project skeleton in under 10 minutes. Nothing generated yet — but everything is ready to build on.

---

## Phase 1A — Synthetic data generation

### What we're checking
The fake dataset is complete, realistic enough for graph analysis, and passes all validation rules.

### Why this eval matters
Everything downstream — graphs, metrics, use cases, dashboard — is built on this data. Bad data produces plausible-looking but meaningless results.

### Why you should care
This is the "foundation inspection." Skipping it means you might build a beautiful dashboard on nonsense.

### How to run it

```bash
make generate                      # or python generator/run_generator.py
make validate                      # or python validator/run_validation.py
```

Review the validation report output.

### Pass criteria — row counts

| Table | Expected range (demo scale) |
|---|---|
| `users` | ~10,000 |
| `items` | ~1,000 |
| `trusted_sources` | ~300 |
| `relationship_edges` | 80,000–200,000 |
| `activity_sessions` | 200,000–500,000 |
| `user_item_interactions` | 150,000–400,000 |
| `contributions` | 8,000–40,000 |
| `contribution_validation_events` | 20,000–60,000 |
| `source_follows` | 30,000–80,000 |
| `feature_exposure_log` | Non-empty (at least one experiment) |
| `planted_influence_rules` | 5 influence families recorded |

### Pass criteria — data quality

| Check | Pass |
|---|---|
| No timestamp violations (event before join, etc.) | Zero violations |
| All foreign keys resolve | Zero orphans |
| Degree distribution is skewed (not flat) | Max degree >> median degree |
| Multiple communities exist (not one blob) | Community count > 1 |
| Activity graph differs from relationship graph | ≥15% of high-frequency activity edges have no relationship edge |
| Cross-org bridges exist | At least some cross-organization edges/sessions |
| Planted rules stored separately | Rules table exists; not merged into model tables |
| Reproducible with same seed | Two runs with same seed produce identical row counts |
| Distribution snapshot printed | Report shows degree histogram, community count, top hubs |

### Fail criteria

- Flat degree distribution (everyone has ~same connections)
- All users in one community
- Timestamp violations > 0
- Missing supporting tables (experiments, churn, onboarding)
- Activity graph identical to relationship graph
- `planted_influence_rules` empty or merged into feature tables

### What success looks like
Validation report prints **PASS** with green checks. Degree histogram shows a long tail (few hubs, many regular users). Community count is in a sensible range (dozens to hundreds, not 1 or 10,000). You can point to a specific hub user and a specific isolated cluster in the report.

> **Added eval:** Distribution snapshot is part of pass criteria, not optional.
>
> **Why added:** Row counts alone don't prove the data is useful. This was flagged in implementation.md — formalizing it here as a hard gate.

> **Added eval:** Activity graph must differ from relationship graph (≥15% stranger co-activity).
>
> **Why added:** Edge case 1.6 in edge-case.md. Without this check, Layer 2 is redundant and several use cases can't be demoed.

---

## Phase 1B — Graph building

### What we're checking
All four graph layers build correctly from the database, projections work, ego networks extract properly, and caches are created.

### Why this eval matters
Graph building is the bridge between flat tables and analysis. Errors here silently drop nodes, double-count edges, or produce empty graphs.

### Why you should care
If graphs are wrong, every centrality score and every dashboard view is wrong — even if the raw data is perfect.

### How to run it

```bash
make build-graphs                  # or python graphs/builder.py
pytest tests/test_graphs.py
```

### Pass criteria

| Check | Pass |
|---|---|
| Layer 1 graph: node count = user count | Match |
| Layer 1 graph: edge count matches DB (after dedup) | Match |
| Layer 2 graph: edges have weights (frequency/duration) | Yes |
| Layer 3 graph: bipartite structure (user + item nodes) | Yes |
| Layer 4 graph: node types labeled (user, source, contribution) | Yes |
| Item-item projection: edges exist above min shared-user threshold | Yes |
| Ego network for a hub user: returns subgraph, not empty | Yes |
| Ego network for orphan user: returns single node (not crash) | Yes |
| Graph cache written to `data/graphs/` | Yes |
| No self-loops in any layer | Zero |
| No references to missing node IDs | Zero |

### Fail criteria

- Graph build crashes on any layer
- Node/edge counts wildly mismatch database
- Ego network extractor crashes on orphan user
- Missing node type labels on Layer 4
- Empty item-item projection

### What success looks like
All four graphs build in under 60 seconds. You can extract an ego network for any user ID programmatically. Cached pickle files exist and reload correctly. A known hub user returns a subgraph with 50+ nodes; a known orphan returns a single node.

> **Added eval:** Ego network size cap — hub user ego network respects max display limit (default 50 nodes).
>
> **Why added:** You approved this as an official decision. Eval must verify truncation works and reports "showing N of M connections."

---

## Phase 1C — NetworkX analytics

### What we're checking
Structural metrics are computed for all layers, cached to disk, and produce sensible values on spot-check.

### Why this eval matters
Use cases read these cached metrics. Wrong or missing metrics mean use cases produce empty lists or nonsense rankings.

### Why you should care
This is the "explain why" engine. If betweenness is all zeros or eigenvector is all NaN, the dashboard has nothing meaningful to show a PM.

### How to run it

```bash
make compute-metrics               # or python analytics/networkx_metrics.py
pytest tests/test_metrics.py       # if exists
```

Review metric summary output.

### Pass criteria

| Check | Pass |
|---|---|
| Betweenness centrality computed for Layers 1, 2, 4 | Files in `data/metrics/` |
| Eigenvector centrality computed for Layers 1, 2, 4 | Files in `data/metrics/` |
| Community detection: >1 community, no all-singletons | Sensible count |
| Connection strength / influence strength computed | Files exist |
| Community-validated influence score computed | File exists |
| Item-item similarity scores computed | File exists |
| Metrics cached (not recomputed on reload) | Reload < 5 seconds |
| Top betweenness node is a plausible bridge | Manual spot-check |
| Top eigenvector node is a plausible hub | Manual spot-check |
| No all-zero or all-NaN metric columns | Zero columns |

### Fail criteria

- Metric computation crashes
- All centrality scores identical (flat data problem upstream)
- All eigenvector scores zero/NaN
- One giant community or all singletons
- Metrics not cached (recomputed every time)

### What success looks like
Metric files exist in `data/metrics/`. Summary report shows top-10 users by betweenness and eigenvector with plausible IDs. Community size distribution shows a mix of small and medium clusters. Metric reload is near-instant.

---

## Phase 1D — Use case engine

### What we're checking
All 8 use cases produce output with explanations and recommended actions. Each respects its toggle rules.

### Why this eval matters
Use cases are the "so what?" layer. This is what a PM actually sees and acts on. A use case that returns empty output or jargon-filled explanations fails the project's purpose.

### Why you should care
If even one use case is broken or empty, the demo has a hole. PMs will focus on what's missing, not what's working.

### How to run it

```bash
pytest tests/test_use_cases.py
python -m use_cases.run_all          # optional: run all and print summary
```

Plus manual review of each use case output.

### Pass criteria — all use cases

Every use case must produce:

| Required output | Pass |
|---|---|
| Flagged nodes or clusters (non-empty list) | Yes |
| Metric values for each flagged item | Yes |
| Plain-language explanation (no raw jargon alone) | Yes |
| Recommended product action | Yes |
| Reference to ego network or subgraph | Yes |

### Pass criteria — per use case

| # | Use case | Specific pass check |
|---|---|---|
| 1 | A/B contamination | At least one cross-variant connected pair flagged; strength score shown; tiered by strength |
| 2 | Champion churn risk | Ranked list with eigenvector + activity; already-churned users excluded |
| 3 | Feature rollout sequencing | Ranked by eigenvector; most/least toggle works |
| 4 | User research prioritization | Ranked by community-validated influence, NOT raw connectivity |
| 5 | Support escalation | Open tickets ranked by user betweenness |
| 6 | Onboarding flow | Binary split: active connection → self-serve; no/inactive connection → guided |
| 7 | Feature discovery gap | At least one cluster flagged as under-exposed (if feature has exposures) |
| 8 | Fraud ring detection | At least one cluster flagged OR explicit "no suspicious clusters" with explanation |

### Fail criteria

- Any use case returns empty output without explanation
- Explanation is only raw metric names (e.g. "eigenvector_centrality: 0.82" with no plain English)
- Toggle shown on exempt use cases (6, 7, 8)
- Onboarding treats inactive/dead connections as active
- Research prioritization ranks by connectivity alone
- Already-churned users appear in churn risk list

### What success looks like
You run all 8 use cases and get 8 non-empty, readable outputs. A non-technical person can read any explanation and understand why the user was flagged and what to do about it.

> **Added eval:** Onboarding use case checks for **active** connections (connected user active within last N days), not just any connection.
>
> **Why added:** You approved this as an official decision. Pass requires stale connections to route to guided onboarding.

> **Added eval:** A/B contamination alerts are **tiered by connection strength**, not binary on/off.
>
> **Why added:** Edge case 4.3. Without tiering, alert fatigue makes the use case demo unusable.

---

## Phase 1E — Dash dashboard

### What we're checking
The PM-facing dashboard loads, all entry paths work, panels update together via callbacks, and no full graph is ever rendered.

### Why this eval matters
The dashboard is the deliverable. Everything else is invisible to the person we're building this for.

### Why you should care
A PM who opens a blank, slow, or confusing dashboard will not care how good the graph analysis is underneath.

### How to run it

```bash
make dashboard                     # or python dashboard/app.py
```

Then follow the manual spot-check script below.

### Manual spot-check script

| # | Action | Expected result |
|---|---|---|
| 1 | Open dashboard | Loads in < 5 seconds |
| 2 | Ranked list: click top user | Graph + explanation panel update |
| 3 | Click a node in graph | Explanation panel updates |
| 4 | Search for a known user | Ego network loads |
| 5 | Switch layer selector (Layer 1 → Layer 2) | Graph updates to different edges |
| 6 | Open use case: A/B contamination | Flagged list with explanations |
| 7 | Toggle most/least important on rollout sequencing | List order reverses |
| 8 | Open onboarding use case | No most/least toggle visible |
| 9 | Select Layer 3 | Table view shown; not forced into node graph |
| 10 | Click hub user with 100+ connections | Graph shows capped view with "showing N of M" |
| 11 | Click orphan user | Message: "no connections found" (not blank panel) |
| 12 | Open dashboard before running pipeline | Message: "data not yet generated" (not empty charts) |

### Pass criteria

| Check | Pass |
|---|---|
| Dashboard starts without error | Yes |
| All 4 entry paths work (ranked list, alerts, search, cluster drill-down) | Yes |
| Core loop: list → graph → explanation | Yes |
| Layer selector toggles graph layers | Yes |
| All 8 use cases visible with correct toggles | Yes |
| Callbacks update panels in < 1 second | Yes |
| No full 10k-node graph rendered | Yes |
| Ego network capped for hub users | Yes |
| Empty states show messages, not blank panels | Yes |
| Layer 3 shows tables, not forced graph | Yes |

### Fail criteria

- Dashboard crashes on load
- Clicking a row/node does nothing (broken callback)
- Full graph rendered (browser hangs)
- Hub user ego network shows 500+ nodes uncapped
- Blank panel with no message for orphan user
- Most/least toggle on exempt use cases
- Callback takes > 5 seconds (live computation in callback)

### What success looks like
You hand the dashboard to someone who hasn't seen the project. They can click around for 5 minutes, find a flagged user, see that user's network, read why they were flagged, and understand the recommended action — without you explaining anything.

> **Added eval:** "Fresh eyes" test — someone unfamiliar with the project completes the spot-check script unaided.
>
> **Why added:** Technical pass criteria don't guarantee PM-legibility. This catches confusing UI that developers miss.

> **Added eval:** Ego network cap visible in UI ("showing 50 of 312 connections").
>
> **Why added:** You approved ego network cap as official. Eval verifies it's implemented and communicated, not just truncated silently.

---

## Phase 1F — Integration and demo readiness

### What we're checking
The full pipeline runs from empty to working dashboard in one command. Fresh-run test passes. Performance meets target.

### Why this eval matters
Individual phases passing in isolation doesn't guarantee they work together. Integration catches stale caches, column mismatches, and sequencing bugs.

### Why you should care
This is the "demo rehearsal." If the full pipeline fails the night before a demo, everything else was wasted.

### How to run it

```bash
rm -rf data/                       # clean slate
make pipeline                      # generate → validate → graphs → metrics → dashboard
```

Then run the Phase 1E spot-check script on the fresh output.

### Pass criteria

| Check | Pass |
|---|---|
| Full pipeline completes without error | Yes |
| Fresh-run (delete data, rerun) produces working dashboard | Yes |
| All 8 use cases show plausible results on fresh data | Yes |
| All 4 entry paths work on fresh data | Yes |
| Dashboard loads in < 5 seconds | Yes |
| No live centrality computation during dashboard use | Yes |
| README: someone else can follow setup instructions | Yes |
| Cache timestamps match data timestamps | Yes |

### Fail criteria

- Pipeline fails at any step
- Fresh-run produces different broken state
- Dashboard shows stale data after regeneration
- Dashboard load > 5 seconds
- README missing or incomplete

### What success looks like
You delete everything, run one command, wait a few minutes, open the dashboard, and the full demo works. You feel confident showing this to someone without live debugging.

---

## Phase 1G — Pre-bugs testing

### What we're checking
All automated checks from `bugs.md` pass — data, graphs, metrics, use cases, wiring, rendering, pipeline, performance, and `.env` config — before any browser-based spot-check.

### Why this eval matters
Most "dashboard looks broken" issues are silent data, cache, or callback problems detectable from the terminal. This phase catches them in minutes instead of hours of clicking.

### Why you should care
Visual testing is expensive. Running the bug runbook first means when you open the browser, you're validating UX — not debugging empty tables or wrong config paths.

### How to run

```bash
# Full runbook: bugs.md §12
python validator/run_validation.py --all
python scripts/check_cache_freshness.py --pre
python graphs/builder.py --all-layers
pytest tests/test_graphs.py tests/test_use_cases.py tests/test_dashboard_callbacks.py -q
python scripts/audit_feature_columns.py
python scripts/check_env.py
pytest tests/ -m integration -q
python scripts/perf_smoke.py
git ls-files .env   # must be empty
```

### Pass criteria

| Check | Pass |
|---|---|
| All runbook commands exit 0 | Yes |
| Zero open CRITICAL/HIGH bugs from bugs.md §13 | Yes |
| BUG-11.xx: `.env` loads and required vars present | Yes |
| BUG-11.xx: `.env` not tracked in git | Yes |

### Fail criteria

- Any pytest or validator failure
- Stale cache, callback mismatch, empty required tables
- `.env` tracked in git

### What success looks like
Terminal is green. You open the browser knowing problems left are likely cosmetic — not missing data or broken plumbing.

**After Phase 1G passes → run Phase 1E manual spot-check from this doc → Phase 1 is demo-ready.**

---

## Phase 2 — PyG predictions

### What we're checking
GNN models train, predict, recover planted influence, and integrate into the dashboard with confidence scores.

### Why this eval matters
Phase 2 is the "what will happen" layer. If models overfit, leak data, or can't recover planted rules, the prediction story is not credible.

### Why you should care
Claiming "the model predicts churn cascades" when it can't beat a baseline or was given the answer key is worse than having no Phase 2 at all.

### Prerequisite
Phase 1F must pass completely. Do not start Phase 2 evals until Phase 1 is demo-ready.

### How to run it

```bash
pip install -r requirements-phase2.txt
make train-models                  # or python analytics/pyg_models.py
make pipeline-full                 # full pipeline including training
pytest tests/test_pyg.py           # if exists
```

### Pass criteria — model training

| Check | Pass |
|---|---|
| NetworkX graphs convert to PyG Data objects (all 4 layers) | Yes |
| Train/val/test split is graph-aware (no neighbor leakage) | Documented and verified |
| Combined adoption model trains without error | Yes |
| Churn cascade model trains without error | Yes |
| Influence propagation model trains without error | Yes |
| Predictions cached to `data/models/` | Yes |
| Dashboard reads cached predictions (no live inference) | Yes |

### Pass criteria — model quality

| Check | Pass |
|---|---|
| Adoption model beats random baseline | Accuracy > random |
| Influence recovery beats baseline | Model finds planted patterns without being given rules |
| Planted rules NOT in model input features | Verified by feature audit |
| Accuracy not suspiciously high (>99%) | Below overfitting threshold |
| Predictions include confidence scores | Yes |

### Pass criteria — dashboard integration

| Check | Pass |
|---|---|
| Explainability panel shows prediction + confidence | Yes |
| Use case 2 (churn) includes forward-looking cascade score | Yes |
| Use case 3 (rollout) includes forward-looking exposure score | Yes |
| When prediction unavailable, falls back to structural explanation | Yes |
| Combined model shows per-layer contribution breakdown | Yes |

### Fail criteria

- Model training crashes
- Random baseline not beaten
- Planted rules found in model features (data leakage)
- Accuracy > 99% with no explanation (overfitting)
- Dashboard runs live GNN inference on click
- Competing separate models give contradictory explanations for same event
- Blank explainability panel when prediction fails

### What success looks like
Models train in reasonable time (< 30 min on dev hardware). Influence recovery report shows the model found known patterns above baseline. Dashboard shows "Prediction confidence: 72%" alongside structural explanation. A PM can see both "why this user matters now" (Phase 1) and "what might happen if they leave" (Phase 2) in the same panel.

**Project is complete when Phase 2 passes.**

> **Added eval:** Feature audit — explicit check that no column in model input matches `planted_influence_rules` parameters.
>
> **Why added:** Edge case 1.8 (critical). Without this, influence recovery validation is meaningless.

> **Added eval:** Overfitting threshold — flag if accuracy > 99%.
>
> **Why added:** Edge case 6.4. Suspiciously perfect accuracy on synthetic data indicates the model memorized generator artifacts, not graph patterns.

> **Added eval:** Prediction fallback — when PyG returns no prediction, dashboard shows Phase 1 structural explanation instead of blank panel.
>
> **Why added:** Edge case 7.5. Explainability is a core design principle; it must never go blank.

---

## Master checklist — quick pass/fail by phase

| Phase | Pass? | Blocker if fail |
|---|---|---|
| 0 — Setup | ☐ | Cannot start any work |
| 1A — Data | ☐ | All downstream phases produce garbage |
| 1B — Graphs | ☐ | No analysis or dashboard possible |
| 1C — Analytics | ☐ | Use cases return empty/wrong results |
| 1D — Use cases | ☐ | Dashboard has nothing meaningful to show |
| 1E — Dashboard | ☐ | No demo possible |
| 1F — Integration | ☐ | Demo unreliable; Phase 1 not done |
| 1G — Pre-bugs testing | ☐ | Silent bugs reach visual testing |
| 2 — PyG | ☐ | No prediction story; project incomplete |

**Rule:** Do not start phase N+1 until phase N passes all criteria.

---

## Summary of flagged additions in this document

Evals not explicitly defined in context.md, architecture.md, or implementation.md:

| # | Addition | Phase | Why added |
|---|---|---|---|
| 1 | Distribution snapshot as hard pass gate | 1A | Row counts alone don't prove realistic data |
| 2 | Activity graph must differ from relationship graph (≥15%) | 1A | Layer 2 redundancy check from edge-case.md |
| 3 | Ego network size cap eval | 1B, 1E | You approved this as official — must verify truncation |
| 4 | Active connection check for onboarding eval | 1D | You approved this as official — stale connections must not pass |
| 5 | A/B contamination tiered by strength | 1D | Prevents alert fatigue in demo |
| 6 | "Fresh eyes" dashboard test | 1E | Technical pass ≠ PM-legible |
| 7 | Ego network cap message in UI ("showing N of M") | 1E | Truncation must be visible, not silent |
| 8 | Cache timestamp vs data timestamp check | 1F | Prevents stale cache silent mismatch |
| 9 | Feature audit (no planted rules in model input) | 2 | Prevents cheating on influence recovery |
| 10 | Overfitting threshold (>99% accuracy flag) | 2 | Catches memorization of generator artifacts |
| 11 | Prediction fallback to structural explanation | 2 | Explainability must never show blank panel |
| 12 | `.env` health check in Phase 0 and 1G | 0, 1G | BUG-11.xx; local config only |

---

## Environment / `.env` evals (cross-phase)

Run in Phase 0 and before any manual spot-check (Phase 1G).

### What we're checking
`.env` loads correctly, required local vars are set, and `.env` stays out of git.

### Why this eval matters
Wrong paths or ports look like dashboard bugs — empty tables, failed startup — but are actually config issues detectable from the terminal.

### How to run

```bash
python scripts/check_env.py
git ls-files .env   # must be empty
```

### Pass criteria

| Check | Pass |
|---|---|
| `check_env.py` exits 0 | Yes |
| `DATABASE_PATH`, `DATA_DIR`, `DASH_PORT` load from `.env` | Yes |
| `.env` not in git | Yes |

### Fail criteria

- Missing `.env` loader / empty required vars
- `.env` committed to repository

### What success looks like
Default clone works with no secrets. `check_env.py` passes after copying `.env.example` to `.env`.

---

## What "done" looks like for the whole project

**Phase 1 done:**
A PM opens the dashboard, explores users and clusters across 4 graph layers, sees all 8 use cases with plain-English explanations, and can make a product decision — without knowing anything about graph theory or Python.

**Project done (Phase 2):**
Same as above, plus the dashboard shows forward-looking predictions with confidence scores. Models demonstrably recover influence patterns planted in the data. A PM sees both "what the network looks like today" and "what might happen tomorrow" in one place.

**In plain English:** Success is not "the code runs." Success is "a PM can open this, understand it, trust it, and act on it."
