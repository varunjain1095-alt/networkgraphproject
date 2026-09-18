# Bugs — Pre-Visual Testing Guide

This document lists bugs that commonly appear **before** you ever open the dashboard in a browser. The goal is to catch them with scripts, logs, and command-line checks — not with your eyes.

Run this checklist at the end of each build phase, and fully before any demo or manual spot-check from `evals.md`.

Each entry includes:
- **What goes wrong**
- **Why it matters**
- **Why you should care**
- **How to test** (before visual testing)
- **How to fix**

---

## How to use this document

| When | What to run |
|---|---|
| **Phase 0** (after setup) | BUG-5.02, BUG-8.01 |
| **Phase 1A** (after data) | §1 Data bugs (BUG-1.01 – 1.07) |
| **Phase 1B** (after graphs) | §1 + §2 Graph bugs |
| **Phase 1C** (after metrics) | §1 + §2 + §3 Analytics bugs |
| **Phase 1D** (after use cases) | §1–§4 |
| **Phase 1E** (after dashboard code) | §1–§6 + §7 subset |
| **Phase 1F** (after integration) | §5–§9 integration/performance |
| **Phase 1G** (pre-bugs testing) | **Full checklist §1–§12** |
| **Phase 2** (after PyG) | §10 ML bugs + full §1–§12 rerun |

**In plain English:** Fix the plumbing before you judge the paint job. Most "the dashboard looks broken" issues start as silent data or wiring problems detectable from the terminal.

---

## Bug-to-phase mapping

| Phase | When to run | Bug IDs |
|---|---|---|
| **0** — Setup | After scaffolding | BUG-5.02, BUG-8.01 |
| **1A** — Data | After each generator sub-step; fully at 1A.8 | BUG-1.01 – BUG-1.07 |
| **1B** — Graphs | After graph build | BUG-2.01 – BUG-2.06 |
| **1C** — Analytics | After metric compute | BUG-3.01 – BUG-3.05 |
| **1D** — Use cases | After each use case module | BUG-4.01 – BUG-4.06 |
| **1E** — Dashboard | After each dashboard step | BUG-5.01, 5.03–5.05, 6.01–6.07, 7.01, 7.03–7.05 |
| **1F** — Integration | After full pipeline | BUG-5.02, 5.06, 7.02, 8.01–8.03, 9.01–9.03 |
| **1G** — Pre-bugs testing | Full regression before visual testing | All §1–§12 (50 bugs) |
| **2** — PyG | After model training + dashboard integration | BUG-1.07, 10.01–10.03, 11.01–11.02 + §1–§12 rerun |

Implementation details per phase: `implementation.md` → **Bugs to test after this phase** under each phase section.

---

## §1 Data layer bugs

Problems in the synthetic dataset before anything reaches the dashboard.

---

### BUG-1.01 Empty or missing tables

**What goes wrong:** Generator finishes but one or more tables have zero rows — e.g. `feature_exposure_log` is empty, so A/B contamination has nothing to analyze.

**Why it matters:** Downstream code often doesn't crash on empty tables; it returns empty lists. Use cases look "working" but show nothing.

**Why you should care:** You open the dashboard, click A/B contamination, see a blank screen, and waste an hour debugging the dashboard when the data was never there.

**How to test:**
```bash
python validator/run_validation.py --check row_counts
# or SQL: SELECT name FROM sqlite_master WHERE type='table';
# then COUNT(*) on each required table
```

**How to fix:** Trace generator step order in `implementation.md` Phase 1A. Ensure supporting event generators (`supporting_events.py`) run and commit. Add a minimum row count assert per table in the validator.

---

### BUG-1.02 Flat data — no hubs, no clusters

**What goes wrong:** Every user has roughly the same number of connections. Centrality scores are all similar. Community detection finds one blob or thousands of singletons.

**Why it matters:** Graph analysis produces technically valid but useless output. Rankings look random.

**Why you should care:** The demo's core pitch — "this user is structurally important" — collapses. Everything looks the same.

**How to test:**
```bash
python validator/run_validation.py --check distribution
# Assert: max_degree / median_degree > threshold (e.g. 5)
# Assert: community_count > 1 AND largest_community < 80% of nodes
```

**How to fix:** Switch from uniform random pairing to preferential attachment in `relationships.py`. Verify `activity_propensity` drives correlated behavior across tables.

---

### BUG-1.03 Timestamp violations

**What goes wrong:** Events exist before users joined, reviews before purchases, sessions before participants existed.

**Why it matters:** Causal logic breaks. Influence and onboarding checks produce wrong results.

**Why you should care:** A careful reviewer spots impossible timelines and loses trust in the entire dataset.

**How to test:**
```bash
python validator/run_validation.py --check timestamps
# Run rules R1–R10 from dataschema.md §11
```

**How to fix:** Add per-row timestamp guards in generator. Run post-generation validation and fail the pipeline on any violation.

---

### BUG-1.04 Orphan foreign keys

**What goes wrong:** `relationship_edges` references a `user_id` not in `users`. Graph build silently drops edges or crashes mid-build.

**Why it matters:** Node/edge counts don't match DB counts. Graph is smaller than expected without explanation.

**Why you should care:** You think you have 150k edges but the graph has 120k — metrics and contamination checks are wrong.

**How to test:**
```sql
SELECT COUNT(*) FROM relationship_edges e
LEFT JOIN users u ON e.user_id_a = u.user_id
WHERE u.user_id IS NULL;
-- repeat for all FK columns
```

**How to fix:** Enforce FK constraints in SQLite (`PRAGMA foreign_keys = ON`). Generator must insert entities before edges.

---

### BUG-1.05 Duplicate edges inflating counts

**What goes wrong:** Both (A,B) and (B,A) stored for undirected relationships, or same pair inserted twice.

**Why it matters:** Connection strength and density metrics double-count. Contamination alerts fire on inflated strength.

**Why you should care:** PM gets false contamination alerts and excludes too many users from experiments.

**How to test:**
```sql
SELECT user_id_a, user_id_b, relationship_type, COUNT(*)
FROM relationship_edges
GROUP BY 1,2,3 HAVING COUNT(*) > 1;
-- For undirected: check canonical ordering (user_id_a < user_id_b)
```

**How to fix:** Canonical sort before insert for undirected types. Add UNIQUE constraint per `dataschema.md` §3.1.

---

### BUG-1.06 Stale config vs data mismatch

**What goes wrong:** `domain_config.yaml` changed but database was generated with old config. Labels say "Feature" but data still reflects gaming entities.

**Why it matters:** Dashboard shows wrong terminology or queries wrong columns.

**Why you should care:** Demo for one company profile shows another company's shape.

**How to test:**
```bash
python -c "
import hashlib, yaml, sqlite3
cfg = yaml.safe_load(open('domain_config.yaml','rb'))
h = hashlib.sha256(yaml.dump(cfg).encode()).hexdigest()
db = sqlite3.connect('data/synthetic.db')
print('config_hash match:', db.execute(
  'SELECT config_hash FROM dataset_metadata'
).fetchone()[0] == h)
"
```

**How to fix:** Regenerate data after config change. Store `config_hash` in `dataset_metadata` at generation time; dashboard startup checks match.

---

### BUG-1.07 `_gen_*` columns leaking into exports

**What goes wrong:** Hidden generator columns (`activity_propensity`, `quality_score`, `popularity_score`) accidentally included in metric exports or model feature CSVs.

**Why it matters:** PyG gets the answer key. Metrics reflect hidden truth instead of observable behavior.

**Why you should care:** Phase 2 influence recovery validation is meaningless if the model sees planted signals directly.

**How to test:**
```bash
python scripts/audit_feature_columns.py
# Assert no column matching _gen_* or planted_influence_rules in data/models/ or PyG export
```

**How to fix:** Explicit allowlist of PyG feature columns. Column exposure matrix in `dataschema.md` §13 as reference.

---

## §2 Graph building bugs

Problems turning database tables into NetworkX graphs.

---

### BUG-2.01 Graph build crashes silently partial

**What goes wrong:** Layer 1 builds, Layer 2 throws, script exits but leaves a stale Layer 1 cache. Dashboard loads old Layer 1 + missing Layer 2.

**Why it matters:** Partial graphs produce partial use case results with no error in the UI.

**Why you should care:** Some use cases work, others show empty — looks like inconsistent product logic, actually a build failure.

**How to test:**
```bash
python graphs/builder.py --all-layers
echo $?  # must be 0
ls data/graphs/layer{1,2,3,4}.gpickle  # all four must exist
python -c "import pickle; [pickle.load(open(f'data/graphs/layer{i}.gpickle','rb')) for i in 1..4]"
```

**How to fix:** Build all layers in one transaction-like step. Delete cache directory before rebuild. Fail pipeline if any layer missing.

---

### BUG-2.02 Node count mismatch (DB vs graph)

**What goes wrong:** `users` has 10,000 rows but Layer 1 graph has 9,950 nodes because 50 users have no edges and were dropped.

**Why it matters:** Orphan users vanish from analysis entirely. Onboarding use case can't find them.

**Why you should care:** New users with no connections — the exact population onboarding targets — don't exist in the graph.

**How to test:**
```python
# After build: assert G.number_of_nodes() == db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
# Users with zero edges should still be nodes (isolates)
```

**How to fix:** Add all entity nodes first, then add edges. Never drop isolates during build.

---

### BUG-2.03 Weighted edges stored as unweighted

**What goes wrong:** Shared activity frequency/duration ignored; all co-play edges weight = 1.

**Why it matters:** Connection strength for contamination is wrong. "500 sessions together" looks the same as "1 session."

**Why you should care:** A/B contamination either over-alerts or under-alerts on the wrong pairs.

**How to test:**
```python
G = load_layer2()
weights = [d.get('weight', 1) for _, _, d in G.edges(data=True)]
assert max(weights) > min(weights), "All edge weights identical"
assert max(weights) > 10, "No high-frequency edges found"
```

**How to fix:** Aggregate `session_count` into edge `weight` in `shared_activity_edges` derivation per `dataschema.md` §4.3.

---

### BUG-2.04 Layer 4 missing node type attributes

**What goes wrong:** Users, sources, and contributions all added as generic nodes with no `node_type` label.

**Why it matters:** Cytoscape renders everything identically. Ego network for a source looks like a user cluster.

**Why you should care:** PM can't interpret the graph. Explainability cites wrong entity types.

**How to test:**
```python
G = load_layer4()
types = set(nx.get_node_attributes(G, 'node_type').values())
assert types >= {'user', 'source', 'contribution'}
```

**How to fix:** Set `node_type` on every node at graph build time. Pass to Cytoscape stylesheet.

---

### BUG-2.05 Ego network extractor returns wrong scope

**What goes wrong:** Requesting 1-hop ego network returns full component or entire graph for hub users.

**Why it matters:** Violates "never render full graph" rule. Browser hangs on render.

**Why you should care:** Click one hub user → dashboard freezes. First impression destroyed.

**How to test:**
```python
hub = get_top_degree_user()
ego = extract_ego_network(hub, radius=1, cap=50)
assert ego.number_of_nodes() <= 50
assert ego.number_of_nodes() < 500
```

**How to fix:** Apply `ego_network_display_cap` from config (default 50). Sort neighbors by edge weight; truncate with metadata `{shown: 50, total: 312}`.

---

### BUG-2.06 Stale graph cache after regeneration

**What goes wrong:** Data regenerated but `data/graphs/*.gpickle` not rebuilt. Dashboard reads old graph.

**Why it matters:** Code and data change; visualization doesn't. Debugging feels cursed.

**Why you should care:** You fix a generator bug, regenerate, dashboard looks identical — you think the fix didn't work.

**How to test:**
```bash
# Compare mtime: synthetic.db vs data/graphs/layer1.gpickle
python scripts/check_cache_freshness.py
# Assert: graph mtime >= db mtime
```

**How to fix:** Pipeline deletes `data/graphs/` before rebuild. `dataset_metadata.generated_at` compared to pickle timestamps at dashboard startup.

---

## §3 Analytics and metrics bugs

Problems in NetworkX computation and cached metrics.

---

### BUG-3.01 Metrics not cached — recomputed every load

**What goes wrong:** Betweenness centrality runs inside a Dash callback or at dashboard startup.

**Why it matters:** 10k nodes × 200k edges betweenness takes minutes. Dashboard hangs.

**Why you should care:** Every page load or click waits 2+ minutes. Unusable before anyone judges the UI.

**How to test:**
```bash
# Dashboard startup should not import heavy betweenness path
grep -r "betweenness_centrality" dashboard/  # should find READ only, not compute
time python dashboard/app.py &
# Startup must complete < 5s with no centrality computation in logs
```

**How to fix:** All centrality computed in `analytics/networkx_metrics.py`, saved to `data/metrics/` or `node_metrics` table. Dashboard reads only.

---

### BUG-3.02 All-zero or NaN metric columns

**What goes wrong:** Eigenvector centrality fails to converge; all values NaN. Use case ranks by NaN → empty or arbitrary order.

**Why it matters:** Use cases 2, 3, 4, 5 depend on centrality. Silent failure.

**Why you should care:** Rollout sequencing shows blank list. PM thinks feature is broken.

**How to test:**
```python
import pandas as pd
m = pd.read_parquet('data/metrics/node_metrics.parquet')
for col in ['betweenness', 'eigenvector']:
    assert m[col].notna().all(), f"{col} has NaN"
    assert m[col].std() > 0, f"{col} is constant"
```

**How to fix:** Fall back to degree centrality on convergence failure with logged warning. Validate metric variance in validator.

---

### BUG-3.03 Metrics computed on wrong graph layer

**What goes wrong:** Support escalation uses Layer 1 betweenness when user's blast radius is through Layer 2 activity edges.

**Why it matters:** Wrong users flagged. Explanation cites wrong edge types.

**Why you should care:** PM prioritizes wrong support ticket. Tool gives bad advice confidently.

**How to test:**
```python
# Unit test: user with high L2 betweenness, low L1 betweenness
# assert support_escalation ranks them high when L2 metric used
assert use_case_5.metric_layer == 'layer2'  # or documented layer
```

**How to fix:** Each use case module declares `required_layers` and `metric_keys`. Unit test per use case with fixture graphs.

---

### BUG-3.04 Community IDs not stable across rebuilds

**What goes wrong:** Same user gets `community_id=3` in metrics cache but `community_id=7` after rebuild. Dashboard cluster drill-down shows wrong group.

**Why it matters:** Cluster views and gap detection reference stale community assignments.

**Why you should care:** "Cluster 3 underserved" points to wrong users after regeneration.

**How to test:**
```bash
# Two metric runs with same seed: community membership identical
python analytics/networkx_metrics.py && cp data/metrics/communities.parquet /tmp/a
python analytics/networkx_metrics.py && diff /tmp/a data/metrics/communities.parquet
```

**How to fix:** Seed Louvain / use deterministic ordering. Recompute communities whenever graphs rebuild; invalidate all community-dependent caches together.

---

### BUG-3.05 `node_metrics` row missing for some users

**What goes wrong:** Metrics computed only for users with degree > 0. Isolates have no row. Dashboard click on orphan throws KeyError or shows blank.

**Why it matters:** Onboarding use case targets low-connection users — exactly those missing metrics.

**Why you should care:** Click orphan user → blank panel. Looks like a front-end bug; actually missing metric row.

**How to test:**
```sql
SELECT COUNT(*) FROM users u
LEFT JOIN node_metrics m ON u.user_id = m.node_id AND m.metric_name = 'degree'
WHERE m.node_id IS NULL;
-- must be 0
```

**How to fix:** Compute metrics for all nodes including isolates (degree=0, betweenness=0, etc.).

---

## §4 Use case engine bugs

Problems in the "so what?" layer before results reach the dashboard.

---

### BUG-4.01 Use case returns empty with no explanation

**What goes wrong:** Module runs, returns `[]`, no message. Dashboard shows empty table.

**Why it matters:** Indistinguishable from "working but nothing flagged" vs "broken."

**Why you should care:** PM can't tell if the tool found nothing or failed.

**How to test:**
```python
for uc in all_use_cases:
    result = uc.run(db, metrics, graphs)
    assert result is not None
    if len(result.flagged) == 0:
        assert result.empty_message is not None  # e.g. "No contamination detected"
```

**How to fix:** Standard interface requires `empty_message` when flagged list is empty. Never return bare empty list.

---

### BUG-4.02 Explanation is raw metric jargon only

**What goes wrong:** Output says `"eigenvector_centrality: 0.8234"` with no plain English.

**Why it matters:** Violates core explainability requirement from context.md.

**Why you should care:** PM can't act on output. Demo fails its purpose.

**How to test:**
```python
result = champion_churn.run(...)
for item in result.flagged:
    assert item.explanation  # non-empty
    assert 'eigenvector' not in item.explanation.lower() or 'important' in item.explanation.lower()
    assert item.recommended_action
```

**How to fix:** Template-based explanations in each use case module. Code review checklist: no raw metric names in user-facing strings.

---

### BUG-4.03 Onboarding treats dead connections as active

**What goes wrong:** User connected to someone who churned 6 months ago → classified as self-serve.

**Why it matters:** Approved product decision (active vs inactive connection) not implemented.

**Why you should care:** Wrong onboarding path for users who actually need help.

**How to test:**
```python
# Fixture: new user with edge to inactive user (last_active > 90 days ago)
result = onboarding_flow.run(...)
assert result.flagged[0].flow_type == 'guided'
assert 'inactive' in result.flagged[0].explanation.lower()
```

**How to fix:** Join `relationship_edges` to `users.last_active_date`. Apply `active_connection_days` threshold from config.

---

### BUG-4.04 Already-churned users in churn risk list

**What goes wrong:** User in `churn_events` still appears in champion churn risk ranking.

**Why it matters:** Recommending retention for someone who already left.

**Why you should care:** Instant credibility loss in demo.

**How to test:**
```python
churned_ids = set(db.execute("SELECT user_id FROM churn_events WHERE churn_date IS NOT NULL"))
flagged_ids = {r.user_id for r in champion_churn.run(...).flagged}
assert churned_ids.isdisjoint(flagged_ids)
```

**How to fix:** Filter `WHERE user_id NOT IN (SELECT user_id FROM churn_events WHERE churn_date IS NOT NULL)`.

---

### BUG-4.05 A/B contamination not tiered by strength

**What goes wrong:** Any shared edge between test/control triggers same alert regardless of weight.

**Why it matters:** Alert fatigue. PM ignores all alerts.

**Why you should care:** Most important use case becomes noise.

**How to test:**
```python
# Weak pair (1 session) vs strong pair (500 sessions) → different alert levels
r = ab_contamination.run(...)
assert r.flagged[strong_pair].alert_level > r.flagged[weak_pair].alert_level
```

**How to fix:** Read `pairwise_connection_strength.combined_strength`. Tier: low / medium / high with thresholds in config.

---

### BUG-4.06 Research prioritization ranks by connectivity not validation

**What goes wrong:** Module sorts by degree or eigenvector instead of community-validated influence score.

**Why it matters:** Use case #4's differentiator disappears.

**Why you should care:** Output identical to rollout sequencing — redundant use case.

**How to test:**
```python
# User A: high degree, zero validations
# User B: low degree, high community_validated_influence
result = research_priority.run(...)
assert rank(result, user_B) < rank(result, user_A)
```

**How to fix:** Use precomputed `community_validated_influence` from `node_metrics` only.

---

## §5 Backend ↔ frontend connection bugs

The dashboard can't reach data, metrics, or use case outputs — even if each works in isolation.

---

### BUG-5.01 Dashboard starts before data exists

**What goes wrong:** `python dashboard/app.py` runs against empty or missing `data/synthetic.db`.

**Why it matters:** Dash renders empty components with no error. Looks like broken UI.

**Why you should care:** First-time setup: install, run dashboard, see blank page, assume project is broken.

**How to test:**
```bash
mv data/synthetic.db /tmp/backup.db 2>/dev/null
python dashboard/app.py &
curl -s localhost:8050 | grep -i "data not yet generated\|run generate"
# Restore db after
```

**How to fix:** Startup hook checks DB exists + `dataset_metadata` row present. Render blocking message component if missing.

---

### BUG-5.02 Wrong file paths between environments

**What goes wrong:** Code uses hardcoded `C:\Projects\...` or relative paths break when run from different cwd.

**Why it matters:** Works on your machine, fails in CI or for another developer.

**Why you should care:** "Works for me" bugs block collaboration and demo rehearsal.

**How to test:**
```bash
cd /tmp && python /path/to/project/dashboard/app.py
# Must still find data/synthetic.db via project-root resolution
```

**How to fix:** Resolve all paths from `PROJECT_ROOT = Path(__file__).resolve().parents[1]`. No absolute user paths in code.

---

### BUG-5.03 Callback references wrong component ID

**What goes wrong:** `Output('graph-view', 'elements')` in callback but layout defines `id='cytoscape-graph'`.

**Why it matters:** Dash silently does nothing on click. No error in browser console sometimes.

**Why you should care:** Click ranked list row → graph never updates. Core loop broken.

**How to test:**
```python
# In tests/test_dashboard_callbacks.py
from dashboard.app import app
assert app.callback_map  # callbacks registered
for cb in app.callback_map.values():
    for out in cb['output']:
        assert component_exists_in_layout(app.layout, out.component_id)
```

**How to fix:** Naming convention doc: all IDs in `layout.py`, callbacks import ID constants from shared `dashboard/ids.py`.

---

### BUG-5.04 Callback fires but returns wrong shape

**What goes wrong:** Cytoscape expects `{'data': {'id': ..., 'label': ...}, 'classes': ...}` but callback returns flat dict or wrong keys.

**Why it matters:** Graph component renders empty or throws JS error.

**Why you should care:** Backend "works" (200 response) but graph is blank — looks like rendering bug, actually data shape bug.

**How to test:**
```python
from dashboard.graph_views import build_cytoscape_elements
elements = build_cytoscape_elements(ego_graph)
for el in elements:
    assert 'data' in el
    assert 'id' in el['data']
# edges: assert 'source' in el['data'] and 'target' in el['data']
```

**How to fix:** Schema validate Cytoscape element list in `graph_views.py` before return. Unit test with known 3-node graph.

---

### BUG-5.05 Store/state not persisting selected node across callbacks

**What goes wrong:** Click user in list → graph updates → click use case tab → selection lost, explanation resets.

**Why it matters:** Multi-panel linked views break. Dash `dcc.Store` not updated or read.

**Why you should care:** PM clicks around and context keeps disappearing. Feels buggy even when individual callbacks work.

**How to test:**
```python
# Dash callback test with dash.testing or manual:
# 1. Click row user_id=X
# 2. Assert dcc.Store('selected-node') == X
# 3. Trigger use-case tab callback
# 4. Assert explanation still references X
```

**How to fix:** Central `selected-node` Store updated by every selection callback. All downstream callbacks read from Store, not local state.

---

### BUG-5.06 Database connection left open or locked

**What goes wrong:** SQLite locked errors when dashboard and generator run concurrently, or connections not closed.

**Why it matters:** Intermittent 500 errors. Hard to reproduce.

**Why you should care:** Demo fails live when someone re-runs generator while dashboard is open.

**How to test:**
```bash
python dashboard/app.py &
python generator/run_generator.py  # should fail gracefully or wait, not corrupt
# Check for sqlite3.OperationalError: database is locked in logs
```

**How to fix:** Read-only connections in dashboard. Context manager for all DB access. Document: stop dashboard before regenerate.

---

## §6 Front-end rendering bugs

Visual issues detectable before manual spot-check — via HTML inspection, callback output, and component tests.

---

### BUG-6.01 Dashboard layout renders blank page

**What goes wrong:** App starts, port open, but `app.layout` is `None` or empty div — white page.

**Why it matters:** Nothing to interact with. Looks like server didn't start.

**Why you should care:** Zero progress visible after Phase 1E work.

**How to test:**
```bash
python dashboard/app.py &
sleep 2
curl -s localhost:8050 | wc -c  # byte count should be >> 500
curl -s localhost:8050 | grep -i "dash\|cytoscape\|ranked"
```

**How to fix:** Verify `app.layout = build_layout()` assigned before `app.run()`. Test layout builds without DB in mock mode.

---

### BUG-6.02 Cytoscape container zero height

**What goes wrong:** Graph data arrives correctly but CSS gives Cytoscape div `height: 0` or no explicit height.

**Why it matters:** Graph is technically rendered but invisible.

**Why you should care:** You stare at empty box thinking graph failed to load. Hours debugging data when it's CSS.

**How to test:**
```bash
curl -s localhost:8050 | grep -A2 cytoscape
# Inspect: style={'width': '100%', 'height': '600px'} minimum
```

**How to fix:** Explicit height on Cytoscape wrapper in `layout.py`. Never rely on auto-height for graph containers.

---

### BUG-6.03 Table component empty despite data in callback

**What goes wrong:** AG Grid / DataTable receives rows in callback but columns misconfigured — wrong `field` names vs data keys.

**Why it matters:** Data exists, table shows headers only or empty rows.

**Why you should care:** Ranked list entry path — primary navigation — appears broken.

**How to test:**
```python
rows = get_ranked_users(limit=10)
columns = ranked_list_columns()
for col in columns:
    assert col['field'] in rows[0], f"Missing field {col['field']}"
```

**How to fix:** Column definitions derived from same schema/dataclass as row builder. Single source of truth for field names.

---

### BUG-6.04 Layer 3 forced into graph view

**What goes wrong:** Selecting Layer 3 triggers Cytoscape render of bipartite user-item graph — unreadable spaghetti.

**Why it matters:** Context says Layer 3 should be table/score based.

**Why you should care:** PM selects "User-Item" layer, sees chaos, assumes tool is low quality.

**How to test:**
```python
# Select layer3 in callback test
output = layer_selector_callback('layer3')
assert output.graph_display == 'hidden' or output.active_panel == 'table'
assert output.table_display == 'visible'
```

**How to fix:** Layer selector switches panel visibility: graph for L1/L2/L4; table for L3 primary view.

---

### BUG-6.05 Most/least toggle shown on exempt use cases

**What goes wrong:** Onboarding, discovery gap, fraud detection show importance toggle that does nothing or sorts nonsense.

**Why it matters:** UI promises behavior it doesn't deliver.

**Why you should care:** Looks like a bug even if data is correct.

**How to test:**
```python
for uc_id in ['onboarding', 'discovery_gap', 'fraud']:
    layout = use_case_panel(uc_id)
    assert 'importance-toggle' not in layout_component_ids(layout)
```

**How to fix:** Toggle rendered only for use cases 1–5 per context.md.

---

### BUG-6.06 Ego network cap not shown in UI

**What goes wrong:** Graph truncated to 50 nodes but UI doesn't say so. PM thinks hub has only 50 connections.

**Why it matters:** Misleading visualization. Approved decision not communicated.

**Why you should care:** PM makes decisions on incomplete picture without knowing it.

**How to test:**
```python
# Hub with 200+ neighbors, cap=50
elements, meta = build_ego_view(hub_id)
assert meta['shown'] == 50
assert meta['total'] > 50
# Layout must include html element displaying meta message
```

**How to fix:** Return `{elements, caption}` from graph builder. Render "Showing 50 of 312 connections" above Cytoscape.

---

### BUG-6.07 Empty states show blank panel not message

**What goes wrong:** Orphan user click → empty graph div, empty explanation div. No text.

**Why it matters:** Indistinguishable from loading or error.

**Why you should care:** PM clicks user, sees nothing, clicks again, gives up.

**How to test:**
```python
result = ego_view_callback('orphan_user_id')
assert 'no connections' in result.explanation.lower() or result.placeholder_visible
```

**How to fix:** Every callback returns explicit empty-state component with message. Never return `[]` or `''` without placeholder.

---

## §7 Data rendering bugs

Data reaches the dashboard but displays wrong values, wrong users, or wrong counts.

---

### BUG-7.01 Wrong user displayed after row click

**What goes wrong:** Click row index 3, graph shows user from index 2 — off-by-one or stale DataFrame index.

**Why it matters:** Explanation doesn't match selected row.

**Why you should care:** PM reads about User A, sees graph for User B. Trust gone.

**How to test:**
```python
rows = fetch_ranked_list()
for i, row in enumerate(rows[:5]):
    graph = ego_view_callback(row['user_id'])  # must pass ID not index
    assert graph.center_node_id == row['user_id']
```

**How to fix:** Callbacks pass `user_id` from row data field, never positional index from pagination.

---

### BUG-7.02 Stale metrics after regeneration

**What goes wrong:** New data generated, old `node_metrics` still on disk. Ranked list shows previous run's top users.

**Why it matters:** Silent desync between DB and displayed rankings.

**Why you should care:** Generator fix invisible in dashboard until someone manually deletes caches.

**How to test:**
```bash
python scripts/check_cache_freshness.py
# node_metrics.computed_at >= dataset_metadata.generated_at
```

**How to fix:** Pipeline step order: generate → validate → graphs → metrics (overwrite). Delete `data/metrics/` on regenerate.

---

### BUG-7.03 Percentages or scores displayed without normalization context

**What goes wrong:** UI shows `0.0045` eigenvector score with no "top 2%" context.

**Why it matters:** Number meaningless to PM.

**Why you should care:** Explainability panel fails its purpose even when value is correct.

**How to test:**
```python
item = explainability.build(user_id)
assert 'top' in item.metric_context.lower() or 'percentile' in item.metric_context.lower()
```

**How to fix:** Format metrics as rank + percentile + plain label in explainability layer, not raw floats.

---

### BUG-7.04 Search returns no results for valid users

**What goes wrong:** Search is case-sensitive or searches wrong column (`user_id` only, not `display_name`).

**Why it matters:** Lookup entry path broken for PMs who don't know internal IDs.

**Why you should care:** PM types a name, gets nothing, assumes user doesn't exist in system.

**How to test:**
```python
user = db.execute("SELECT display_name, user_id FROM users LIMIT 1").fetchone()
assert search(user['display_name'].lower())  # case insensitive
assert search(user['user_id'])
```

**How to fix:** `LIKE LOWER(?)` on `display_name` and exact match on `user_id`. Trim whitespace.

---

### BUG-7.05 Use case shows wrong count in header

**What goes wrong:** "12 users flagged" in header but table has 8 rows — pagination or filter mismatch.

**Why it matters:** PM doesn't know if data is missing or miscounted.

**Why you should care:** Header count vs table rows disagreement looks like a data bug.

**How to test:**
```python
result = use_case.run()
header_count = parse_header(result.header_text)
assert header_count == len(result.flagged)
```

**How to fix:** Header text generated from `len(flagged)` same list passed to table. Single result object, no re-query.

---

## §8 Pipeline and integration bugs

End-to-end wiring failures before anyone opens a browser.

---

### BUG-8.01 Pipeline step order wrong

**What goes wrong:** Metrics computed before graphs built, or dashboard started before metrics cached.

**Why it matters:** Each step depends on previous. Wrong order → empty or stale inputs.

**Why you should care:** `make pipeline` succeeds but dashboard shows zeros.

**How to test:**
```bash
make pipeline 2>&1 | tee /tmp/pipeline.log
grep -E "generate|validate|build-graphs|compute-metrics|dashboard" /tmp/pipeline.log
# Assert order matches implementation.md Phase 1F
```

**How to fix:** Makefile dependencies enforce order. Each step checks prerequisite artifacts exist.

---

### BUG-8.02 Partial pipeline failure leaves dirty state

**What goes wrong:** Graph build fails halfway; next run uses mixed old/new files.

**Why it matters:** Non-deterministic behavior between runs.

**Why you should care:** "It worked yesterday" bugs — impossible to debug.

**How to test:**
```bash
# Simulate failure mid-pipeline, rerun
make pipeline; echo exit:$?
# Assert: either full success or clean rollback with clear error
```

**How to fix:** Write to temp dir, atomic rename on success. Or delete all outputs at pipeline start.

---

### BUG-8.03 Tests pass but don't cover integration path

**What goes wrong:** Unit tests mock DB/graphs. Real pipeline never exercised in CI.

**Why it matters:** Mocks hide wiring bugs (BUG-5.x, BUG-8.x).

**Why you should care:** Green tests, broken demo.

**How to test:**
```bash
pytest tests/ -m "not integration"  # unit only
pytest tests/ -m integration         # must exist and run on fresh data
```

**How to fix:** At least one integration test: generate mini dataset → build graphs → compute metrics → run one use case → assert non-empty.

---

## §9 Performance bugs (detectable without visual testing)

---

### BUG-9.01 Dashboard startup > 5 seconds

**What goes wrong:** App loads entire graph pickle or recomputes metrics at import time.

**Why it matters:** evals.md Phase 1F performance gate fails.

**Why you should care:** Demo opens slowly; PM already skeptical.

**How to test:**
```bash
time (python dashboard/app.py & sleep 1; curl -s -o /dev/null -w "%{time_total}" localhost:8050)
```

**How to fix:** Lazy load graphs on first selection, not at import. Precomputed metrics only.

---

### BUG-9.02 Callback response > 1 second

**What goes wrong:** Callback triggers graph rebuild or SQL full-table scan.

**Why it matters:** UI feels frozen on every click.

**Why you should care:** PM clicks three times, nothing happens, leaves.

**How to test:**
```python
# dash.testing: measure callback duration
with app.run_server():
    start = time.time()
    dash_duo.find('#row-0').click()
    dash_duo.wait_for_element('#cytoscape-graph')
    assert time.time() - start < 1.0
```

**How to fix:** Index all lookup columns. Preload ranked list into memory at startup or paginate. Never rebuild graph in callback.

---

### BUG-9.03 Memory blow-up loading full graph pickle

**What goes wrong:** Dashboard loads all 4 layer pickles (multi-GB) at startup.

**Why it matters:** OOM on laptop. Process killed silently.

**Why you should care:** Dashboard "doesn't start" on demo machine — no error message.

**How to test:**
```bash
/usr/bin/time -v python -c "from dashboard.data import load_graphs; load_graphs()"
# Max RSS should stay reasonable (< 2GB at demo scale)
```

**How to fix:** Load layer on demand when selected. Ego networks extracted from disk/SQL, not full graph in memory.

---

## §10 ML / Phase 2 bugs (pre-visual)

---

### BUG-10.01 Planted rules in model feature matrix

**What goes wrong:** Feature export joins `planted_influence_rules` or `_gen_*` columns.

**Why it matters:** Influence recovery eval is invalid.

**Why you should care:** Phase 2 core proof fails silently.

**How to test:**
```bash
python scripts/audit_feature_columns.py --phase2
```

**How to fix:** Allowlist features. Automated test fails if forbidden columns present.

---

### BUG-10.02 Random train/test split (neighbor leakage)

**What goes wrong:** Users in test set connected to users in train set.

**Why it matters:** Accuracy inflated 10–30%. Demo claims don't hold up.

**Why you should care:** Technical reviewer catches it immediately.

**How to test:**
```python
# For each test node: no neighbor in train set
assert no_cross_split_edges(train_nodes, test_nodes, graph)
```

**How to fix:** Cluster-based or edge-masked split per implementation.md Phase 2.

---

### BUG-10.03 Predictions not cached — live inference in callback

**What goes wrong:** Same class of bug as BUG-3.01 but for PyG.

**Why it matters:** Click user → 30s GNN inference.

**Why you should care:** Phase 2 dashboard unusable.

**How to test:**
```bash
grep -r "model.forward\|predict(" dashboard/
# should return zero hits
```

**How to fix:** Batch inference in training step → `data/models/predictions.parquet`. Dashboard reads parquet.

---

## §11 Environment configuration bugs

Problems with `.env` loading and local runtime config. This project uses no external APIs — only path, seed, and dashboard settings.

---

### BUG-11.01 `.env` not loaded or missing required vars

**What goes wrong:** Code reads `os.environ` directly but nothing loads `.env` on startup. Vars are empty; app uses wrong defaults or crashes.

**Why it matters:** DB paths and ports silently wrong.

**Why you should care:** Works on one machine with exported shell vars; fails for everyone else cloning the repo.

**How to test:**
```bash
python -c "from config.env import load_env; load_env(); import os; assert os.getenv('DATABASE_PATH')"
python scripts/check_env.py
```

**How to fix:** Central `config/env.py` using `python-dotenv`. Call `load_env()` at entry point of every script and `dashboard/app.py`.

---

### BUG-11.02 `.env` tracked in git

**What goes wrong:** `.env` with local overrides tracked in git.

**Why it matters:** Local config leaks into shared repo; teammates inherit wrong paths.

**Why you should care:** Portfolio repo may expose machine-specific settings or accidental secrets.

**How to test:**
```bash
git ls-files .env          # must return nothing
```

**How to fix:** `.gitignore` includes `.env`. Only commit `.env.example`. Use env vars in CI.

---

## §12 Pre-bugs testing runbook

Single command sequence before any visual/manual testing from `evals.md`.

```bash
# 1. Data
python validator/run_validation.py --all
python scripts/check_cache_freshness.py --pre

# 2. Graphs
python graphs/builder.py --all-layers
pytest tests/test_graphs.py -q

# 3. Metrics
python analytics/networkx_metrics.py
pytest tests/test_metrics.py -q

# 4. Use cases
pytest tests/test_use_cases.py -q

# 5. Backend/frontend wiring
pytest tests/test_dashboard_callbacks.py -q
python scripts/audit_feature_columns.py

# 6. Integration (mini)
pytest tests/ -m integration -q

# 7. Performance smoke
python scripts/perf_smoke.py

# 8. Environment / .env
python scripts/check_env.py
git ls-files .env   # must be empty
```

**Pass:** All commands exit 0. No CRITICAL or HIGH bugs from §1–§11 open.

**Fail:** Any command non-zero → fix before opening browser.

---

## §13 Bug severity quick reference

| ID range | Category | Fix before visual testing? |
|---|---|---|
| BUG-1.xx | Data | **Yes — always** |
| BUG-2.xx | Graph build | **Yes — always** |
| BUG-3.xx | Metrics | **Yes — always** |
| BUG-4.xx | Use cases | **Yes — always** |
| BUG-5.xx | Backend ↔ frontend | **Yes — always** |
| BUG-6.xx | Front-end rendering | **Yes — mostly automatable** |
| BUG-7.xx | Data rendering | **Yes — mostly automatable** |
| BUG-8.xx | Pipeline | **Yes — always** |
| BUG-9.xx | Performance | **Yes — before demo** |
| BUG-10.xx | ML / Phase 2 | **Yes — before Phase 2 demo** |
| BUG-11.xx | Environment / `.env` | **Yes — always** |

---

## Flagged additions in this document

| # | Addition | Why |
|---|---|---|
| 1 | `dashboard/ids.py` shared component ID constants | Prevents BUG-5.03 callback ID mismatch |
| 2 | `scripts/check_cache_freshness.py` | Prevents stale graph/metrics bugs (2.06, 7.02) |
| 3 | `scripts/audit_feature_columns.py` | Prevents _gen_* / planted rule leakage |
| 4 | `scripts/perf_smoke.py` | Automates BUG-9.xx checks |
| 5 | `empty_message` required on use case interface | Prevents BUG-4.01 silent empty |
| 6 | `tests/test_dashboard_callbacks.py` | Catches BUG-5.x without browser |
| 7 | Integration test marker `-m integration` | Prevents BUG-8.03 false confidence |
| 8 | `config/env.py` + `.env.example` | Central env loading; BUG-11.01, 11.02 |
| 9 | `scripts/check_env.py` | BUG-11.01, 11.02 |

---

## Relationship to other docs

| Doc | Role |
|---|---|
| `edge-case.md` | Describes corner scenarios and design risks |
| `bugs.md` (this file) | Common failure modes + pre-visual detection/fix |
| `evals.md` | Phase pass/fail gates including manual spot-checks |
| `implementation.md` Phase 1G | When to run this checklist in the build |
| `.env.example` | Template for local runtime config |

**In plain English:** `edge-case.md` says what can go wrong in theory. `bugs.md` says what actually breaks in practice and how to catch it from the terminal. `evals.md` says when you're allowed to move on. Run bugs.md checks **before** evals.md manual spot-checks.
