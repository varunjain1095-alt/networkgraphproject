# Edge Cases — Network Graph Intelligence Project

This document lists corner scenarios that can break, mislead, or silently weaken the project. Each entry explains the situation in plain English, why it matters, and why you should care.

Use this during build and review: if an edge case is not handled, the demo may look fine but give wrong answers.

---

## How to read this document

Each edge case follows the same structure:

| Field | Meaning |
|---|---|
| **Scenario** | What can go wrong |
| **Why it matters** | What breaks or becomes misleading |
| **Why you should care** | The practical impact on the demo, a PM, or a product decision |

Edge cases are grouped by project layer. Severity is noted where helpful:

- **Critical** — can produce wrong decisions or crash the system
- **High** — results look plausible but are misleading
- **Medium** — degraded experience or weaker insights
- **Low** — edge of scope, but worth knowing

---

## 1. Data generation edge cases

These happen while creating the synthetic dataset.

---

### 1.1 Flat, uniform random data (no hubs, no clusters)

**Scenario:** Users, edges, and item ownership are generated uniformly — everyone has roughly the same number of connections and items.

**Why it matters:** Centrality scores converge to similar values. Community detection finds meaningless groups. The dashboard shows "everyone is equally important," which defeats the purpose of graph analysis.

**Why you should care:** The demo would look like it works but teach nothing. A PM would correctly say "this tool doesn't tell me anything I couldn't get from a spreadsheet."

**Severity:** Critical

---

### 1.2 Impossible timestamps

**Scenario:** A user reviews an item before owning it, co-plays with someone before either has joined, or an influence effect happens before the relationship existed.

**Why it matters:** Breaks causal logic. Use cases that depend on timing (onboarding, rollout sequencing, influence propagation) produce nonsense. Validation should catch this, but if it doesn't, downstream analysis inherits the error.

**Why you should care:** One bad timestamp can make an entire user's history unbelievable. If a PM spots "this user reviewed a product before they had access," they lose trust in the whole tool.

**Severity:** Critical

---

### 1.3 Orphan users (zero connections, zero activity)

**Scenario:** Some users exist in the `users` table but have no relationships, no sessions, no item interactions, and no contributions.

**Why it matters:** They appear in counts but are invisible in every graph layer. Ego networks for these users are empty. Centrality is zero or undefined. Several use cases have nothing to say about them.

**Why you should care:** Onboarding flow (#6) and feature discovery gap (#7) specifically apply to low-connection users. If there are no such users — or only broken ones — those use cases can't be demonstrated properly.

**Severity:** High

**What to do:** Allow a small, intentional orphan population (new users, inactive signups). Don't accidentally create orphans through generation bugs.

---

### 1.4 Super-hubs that dominate everything

**Scenario:** One or two users have thousands of connections while everyone else has almost none — far beyond the intended power-law skew.

**Why it matters:** Eigenvector and betweenness scores collapse: the hub gets ~100% of the importance, everyone else looks irrelevant. Community detection may put the entire graph in one cluster centered on the hub.

**Why you should care:** Rollout sequencing and champion churn would always point to the same 1–2 users. The demo looks broken, not insightful.

**Severity:** High

**What to do:** Cap maximum degree during generation. Validate degree distribution has a long tail, not a single spike.

---

### 1.5 Duplicate or bidirectional relationship edges

**Scenario:** User A → User B and User B → User A both exist as separate rows, or the same pair appears twice with different types.

**Why it matters:** Edge counts inflate. Density and reciprocity metrics double-count. Contamination detection may flag pairs that look stronger than they are.

**Why you should care:** A/B contamination alerts become unreliable — you might exclude users who aren't actually strongly connected, or miss real contamination because the graph is noisy.

**Severity:** High

**What to do:** Decide per relationship type: directed or undirected. Deduplicate during graph build. Document the rule in domain config.

---

### 1.6 Activity graph identical to relationship graph

**Scenario:** 100% of shared activity sessions are between existing friends/connections — no stranger sessions at all.

**Why it matters:** Layer 1 and Layer 2 become redundant. "Stronger connection recommendation" (co-play without friendship) never fires. The value of having two separate layers disappears.

**Why you should care:** You lose the ability to demo "people who play together but aren't friends — maybe they should connect." The architecture's multi-layer design becomes pointless on this data.

**Severity:** High

**What to do:** Enforce the 70–80% / 20–30% split from context.md. Validate that a meaningful share of high-frequency activity edges have no corresponding relationship edge.

---

### 1.7 Planted influence too strong or too weak

**Scenario:** Influence rules are so strong that every connected user always copies behavior, or so weak they're indistinguishable from random noise.

**Why it matters:** Too strong: PyG recovery is trivially easy — proves nothing. Too weak: PyG can't recover the pattern — looks like the mechanism failed when the data was the problem.

**Why you should care:** Phase 2's core validation ("can the model find influence we planted?") becomes meaningless. You can't tell if the model is bad or the data is bad.

**Severity:** High (Phase 2)

**What to do:** Tune effect size during generation. Validate with a simple correlation check before training GNNs.

---

### 1.8 Planted rules leaked into model inputs

**Scenario:** `planted_influence_rules` table or its parameters accidentally get joined into features fed to PyG.

**Why it matters:** The model gets the answer key. Recovery validation becomes a cheat, not a test.

**Why you should care:** The entire Phase 2 credibility story collapses. You'd be demoing "the model finds influence" when you literally told it where the influence is.

**Severity:** Critical (Phase 2)

**What to do:** Keep rules table strictly separate. Add an explicit validation check that no model feature column matches rule parameters.

---

### 1.9 Referral inferred instead of planted

**Scenario:** Referral relationships are guessed from join timing or connection order instead of stored as ground-truth metadata.

**Why it matters:** Context explicitly says referral cannot be defensibly inferred. Inferred referrals will be wrong often and can't be validated.

**Why you should care:** Any demo or write-up claiming "referral tracking" would be on shaky ground. A reviewer could correctly challenge the methodology.

**Severity:** Medium

---

### 1.10 Cross-organization bridges missing

**Scenario:** Every user only connects within their own organization. No cross-org relationships, shared sessions, or shared channels.

**Why it matters:** Cross-org contamination in A/B tests, cross-org rollout effects, and bridge-user detection all become undemoable. The "multi-organization" requirement from context is unmet.

**Why you should care:** For a generic company tool, siloed orgs make the prototype feel like a single-company toy, not a reusable system.

**Severity:** Medium

**What to do:** Intentionally seed a small number of cross-org bridges (relationships, shared sessions, shared items).

---

### 1.11 New items with zero interaction history

**Scenario:** Items exist in the `items` table but no user has interacted with them yet.

**Why it matters:** Cold-start recommendation (#Layer 3) and bundle analysis have nothing to work with for these items. Item-item projections return empty.

**Why you should care:** Cold-start is a named capability. If every item has history, you never demo the hardest and most useful case: "a new feature just launched — who should get it?"

**Severity:** Medium

**What to do:** Include a small set of recently released items with low or zero adoption at the simulation's end date.

---

### 1.12 Reproducibility breaks across runs

**Scenario:** Two generation runs with the same config produce different data because random seeds aren't fixed or aren't propagated to all sub-generators.

**Why it matters:** Debugging becomes impossible. A bug found in run A can't be reproduced in run B. Tests become flaky.

**Why you should care:** Every time you regenerate data, previously working dashboard views or use case results may change for no code reason. You waste time chasing ghosts.

**Severity:** Medium

**What to do:** Single master seed in config. Log seed with each generated dataset.

---

## 2. Graph building edge cases

These happen when turning database tables into NetworkX graph objects.

---

### 2.1 Disconnected graph components

**Scenario:** The graph splits into several islands with no paths between them.

**Why it matters:** Betweenness and shortest-path metrics behave differently on disconnected graphs. Some nodes have infinite distance to others. Global rankings mix nodes from separate worlds.

**Why you should care:** Feature discovery gap (#7) and contamination detection may miss cross-component issues entirely. A PM exploring one cluster never sees the others.

**Severity:** High

**What to do:** Report component count during graph build. Allow disconnected graphs (realistic) but surface component ID in dashboard. Don't assume one connected graph.

---

### 2.2 Self-loops or invalid node references

**Scenario:** An edge points from a user to themselves, or references a `user_id` that doesn't exist in the `users` table.

**Why it matters:** Many graph algorithms assume simple graphs without self-loops. Missing nodes cause silent drops or crashes during build.

**Why you should care:** A single bad edge can crash the dashboard when you click on a affected node, or silently shrink the graph without warning.

**Severity:** Critical

**What to do:** Validate referential integrity in Phase 1A. Strip self-loops during graph build with a logged warning.

---

### 2.3 Mixed node types in one graph without labeling

**Scenario:** Layer 4 combines users, sources, and contributions in one graph but doesn't tag node types.

**Why it matters:** Centrality rankings mix apples and oranges — a contribution node might rank above a user. Ego network views show confusing structures.

**Why you should care:** The PM sees a graph full of nodes they can't interpret. Explainability breaks down.

**Severity:** High

**What to do:** Every node gets a `node_type` attribute. Dashboard renders different shapes/colors per type.

---

### 2.4 Weighted vs unweighted edge confusion

**Scenario:** Shared activity edges have frequency/duration weights, but centrality is computed on an unweighted version (or vice versa).

**Why it matters:** Connection strength for contamination detection depends on weights. Rollout sequencing on unweighted graphs treats a one-time session the same as 500 sessions.

**Why you should care:** A/B contamination (#1) might under-flag a pair that co-played once (low risk) or over-flag a pair with one shared session vs. 500 (very different real-world risk).

**Severity:** High

**What to do:** Document which metrics use weighted vs unweighted graphs. Be consistent. Expose weight in explainability panel.

---

### 2.5 Bipartite projection produces empty or complete graphs

**Scenario:** Item-item projection from Layer 3 yields either no edges (no shared users) or a near-complete graph (every item shares users with every other item).

**Why it matters:** Recommendations become either "nothing similar" or "everything similar." Clustering is trivial or impossible.

**Why you should care:** "People who use X also use Y" — the most intuitive demo in Layer 3 — either shows blank or useless results.

**Severity:** High

**What to do:** Set minimum shared-user threshold for projection edges. Validate projection density after build.

---

### 2.6 Ego network too large or too small

**Scenario:** A hub user's ego network (1-hop neighbors) includes 500+ nodes. Or a peripheral user's ego network is a single isolated node.

**Why it matters:** Cytoscape can't render 500 nodes meaningfully. An empty ego network makes the dashboard look broken.

**Why you should care:** Context says never render the full graph. If ego networks for hub users are huge, you've violated that rule through the back door.

**Severity:** High

**What to do:** Cap ego network radius or apply importance filtering (top N neighbors by edge weight). Show "showing 50 of 312 connections" with expand option.

> **Added edge case:** Ego network size cap with explicit truncation message in dashboard.
>
> **Why added:** Context says filtered views only but doesn't specify max ego network size. Without a cap, hub users break the visualization.

---

### 2.7 Stale graph cache after data regeneration

**Scenario:** Data is regenerated but cached graph pickles in `data/graphs/` are not rebuilt. Dashboard shows old graph.

**Why it matters:** Silent mismatch between database and visualization. Metrics and graphs disagree.

**Why you should care:** You change the generator, regenerate, open dashboard — everything looks the same. You think your change didn't work. Hours wasted.

**Severity:** High

**What to do:** Pipeline script deletes or invalidates caches on regeneration. Include cache timestamp vs data timestamp check.

---

## 3. NetworkX analytics edge cases

These happen while computing centrality, communities, and paths.

---

### 3.1 Betweenness centrality on large graphs is extremely slow

**Scenario:** Computing betweenness on 10k nodes and 200k edges takes many minutes or runs out of memory.

**Why it matters:** If computed live on dashboard load, the app hangs. Context assumes precomputed caching for this reason.

**Why you should care:** A PM waiting 5 minutes for a page load will close the tab. The demo dies regardless of how good the analysis is.

**Severity:** Critical (if not cached)

**What to do:** Precompute and cache. Consider approximate betweenness for large graphs if exact is too slow.

---

### 3.2 All eigenvector centrality scores are zero or NaN

**Scenario:** Graph has no convergent eigenvector (e.g., directed acyclic structure, or disconnected with isolated nodes).

**Why it matters:** Rollout sequencing (#3) and champion churn (#2) depend on eigenvector centrality. Empty scores mean those use cases produce nothing.

**Why you should care:** Two of your eight use cases silently fail. The dashboard shows blank lists with no error message.

**Severity:** High

**What to do:** Fall back to degree centrality with a logged warning. Surface "metric unavailable for this subgraph" in dashboard.

---

### 3.3 Community detection returns one giant cluster

**Scenario:** Louvain (or similar) assigns all 10k users to a single community.

**Why it matters:** Cluster drill-down entry path shows one bubble. Feature discovery gap can't identify isolated segments. Fraud detection can't distinguish rings from the mass.

**Why you should care:** The dashboard's "explore by cluster" path — one of four entry points — becomes useless.

**Severity:** High

**What to do:** Validate community count and size distribution after detection. If only one community, flag in validation report — likely a data generation problem (see 1.1).

---

### 3.4 Community detection returns only singletons

**Scenario:** Every user is their own community (5000 communities of 1 user each).

**Why it matters:** Opposite of 3.3. Cluster views show noise. Density/reciprocity for fraud detection has no meaningful groups to analyze.

**Why you should care:** Fraud ring detection (#8) needs groups to inspect. With all singletons, it flags nothing or everything.

**Severity:** High

**What to do:** Same as 3.3 — validate community size distribution. Usually indicates data is too sparse or too random.

---

### 3.5 Ties in ranked lists

**Scenario:** Fifty users all have eigenvector centrality of exactly 0.0045.

**Why it matters:** "Most important" and "least important" toggles show arbitrary order. PM can't tell who matters more.

**Why you should care:** Ranked list entry path — a primary dashboard entry point — looks broken or random when there are ties.

**Severity:** Medium

**What to do:** Use secondary sort key (e.g., activity level, degree). Show "tied at rank 15" in UI. Never rely on sort stability alone.

---

### 3.6 Metrics computed on wrong graph layer

**Scenario:** Support escalation (#5) uses betweenness from Layer 1 (relationships) when the user's importance is actually in Layer 2 (shared activity).

**Why it matters:** The flagged user may not be the real bridge in the relevant context. Explanation cites wrong edge types.

**Why you should care:** PM acts on the wrong person. The explainability panel says "high betweenness in relationship graph" but the user's real influence is through co-play sessions.

**Severity:** High

**What to do:** Each use case document which layer(s) it reads. Dashboard layer selector should affect use case metrics when appropriate.

---

### 3.7 Community-validated influence score for users with no contributions

**Scenario:** A highly connected user has never posted or contributed anything. Community-validated influence score is zero despite high connectivity.

**Why it matters:** User research prioritization (#4) ranks them low. But a PM might still want to interview them for connectivity alone.

**Why you should care:** The use case is specifically about validated influence, not raw connectivity — but a PM might not understand the distinction and think the tool missed an obvious candidate.

**Severity:** Medium

**What to do:** Explanation must say "no contributions to validate — ranking based on network position only" when connectivity is high but validation is zero. Don't silently rank them last.

---

## 4. Use case edge cases

Corner scenarios specific to each of the 8 product decisions.

---

### 4.1 A/B contamination — no experiment data exists

**Scenario:** `feature_exposure_log` is empty or has only one variant.

**Why it matters:** Contamination detection has nothing to compare. No test/control pairs to check.

**Why you should care:** Use case #1 — often the lead demo use case — shows a blank screen. PM asks "where are the experiment alerts?"

**Severity:** High

**What to do:** Generator must create at least one experiment with meaningful test/control splits. Validate in Phase 1A.

---

### 4.2 A/B contamination — all test users are isolated

**Scenario:** Experiment assignment happens to put all connected pairs in the same variant group by luck.

**Why it matters:** Contamination detection finds zero violations. Demo shows "all clear" which looks like the tool works but never demonstrates the alert case.

**Why you should care:** The most compelling demo moment — "your test is contaminated, here are the pairs" — never happens.

**Severity:** Medium

**What to do:** Seed at least some intentional cross-variant connected pairs during experiment data generation. Or accept that on random data it may not always fire, and have a known example ready.

---

### 4.3 A/B contamination — weak connection flagged same as strong

**Scenario:** A pair with one shared session 2 years ago gets the same contamination alert as a pair with 500 sessions and daily interaction.

**Why it matters:** Context says nodes should be classified by connection/influence strength. Treating all connections equally produces noisy alerts.

**Why you should care:** PM gets alert fatigue. They exclude users unnecessarily, shrinking the experiment cohort until results are meaningless.

**Severity:** High

**What to do:** Tier alerts by strength threshold. Show strength score in explanation. Recommend exclusion only above a configurable cutoff.

---

### 4.4 Champion churn — user already churned

**Scenario:** A user with high eigenvector centrality is already in `churn_events`.

**Why it matters:** Flagging them as "at risk" is wrong — they already left. Cascade analysis should shift to "damage assessment" not "prevention."

**Why you should care:** PM sees a churn risk alert for someone who already left. Credibility gone.

**Severity:** High

**What to do:** Exclude already-churned users from risk ranking (or move them to a separate "post-churn cascade" view in Phase 2).

---

### 4.5 Champion churn — high centrality but inactive

**Scenario:** A user has high eigenvector centrality from past connections but hasn't been active in months.

**Why it matters:** Context says churn risk combines eigenvector + activity signal. Centrality alone overstates risk for ghosts.

**Why you should care:** PM wastes retention effort on someone who is structurally important but already disengaged — or misses the weighting nuance entirely.

**Severity:** Medium

**What to do:** Apply activity decay. Explanation must show both centrality and recent activity level.

---

### 4.6 Rollout sequencing — rolling out to hubs first spreads too fast

**Scenario:** Top eigenvector nodes are selected for rollout, but they're connected to everyone — feature spreads instantly, leaving no control group for comparison.

**Why it matters:** The tool recommends a rollout order that makes measurement impossible.

**Why you should care:** PM follows the recommendation and loses the ability to measure impact. The tool created a problem instead of solving one.

**Severity:** High

**What to do:** Offer rollout strategies: "maximize spread" vs "maximize measurable signal." Explain tradeoff in recommended action.

> **Added edge case:** Rollout strategy modes (spread vs measurement).
>
> **Why added:** Context says rollout sequencing uses eigenvector centrality but doesn't address the measurement tradeoff. Worth flagging so the tool doesn't naively optimize for one goal.

---

### 4.7 User research prioritization — popularity mistaken for validated influence

**Scenario:** A user with many connections gets high visibility, but their contributions are never validated by peers. Raw connectivity ranking would put them first; validated influence ranking puts them last.

**Why it matters:** This is the entire point of use case #4 — distinguishing connectivity from validated influence.

**Why you should care:** If the tool conflates the two, it's no better than sorting by follower count. The differentiator of this use case disappears.

**Severity:** High

**What to do:** Strictly use community-validated influence metric. Explanation must explicitly say "connectivity is high but peer validation is low."

---

### 4.8 Support escalation — ticket from peripheral user during outage

**Scenario:** A major outage generates thousands of tickets. Betweenness ranking buries the critical bridge user's ticket among mass peripheral complaints.

**Why it matters:** During incidents, volume overwhelms centrality-based ranking.

**Why you should care:** The whole point of blast-radius prioritization fails exactly when it matters most — during a crisis.

**Severity:** Medium

**What to do:** Combine centrality with severity and recency. Allow filtering by time window. Don't rely on centrality alone during high-volume events.

---

### 4.9 Onboarding — user has connection but connection is inactive

**Scenario:** New user has a relationship edge to someone who churned months ago.

**Why it matters:** Binary "has existing connection" check says self-serve. But the connection can't actually help them ramp.

**Why you should care:** PM sends new user to self-serve onboarding based on a dead connection. User struggles, churns early.

**Severity:** Medium

**What to do:** Extend binary check: "has active connection" (connected to someone active in last N days). Show connection status in explanation.

> **Added edge case:** Active vs inactive connection for onboarding.
>
> **Why added:** Context defines binary existing-connection signal but doesn't address stale connections. Real products have this constantly.

---

### 4.10 Feature discovery gap — feature reached hub but not periphery

**Scenario:** Feature exposure follows hub nodes, so exposure metrics look good globally, but entire peripheral clusters never received it.

**Why it matters:** Global exposure rate hides local isolation. Gap detection must work at cluster level, not global level.

**Why you should care:** PM concludes "feature reached 80% of users" and kills a feature that was never shown to 3 entire teams.

**Severity:** High

**What to do:** Measure exposure per community, not just globally. Flag clusters below exposure threshold.

---

### 4.11 Feature discovery gap — feature not yet rolled out to anyone

**Scenario:** Feature exists in the system but `feature_exposure_log` has zero exposures.

**Why it matters:** Every cluster looks "isolated" from exposure. Gap detection flags everything.

**Why you should care:** Demo shows "every cluster is underserved" which is technically true but useless — the feature hasn't launched yet.

**Severity:** Medium

**What to do:** Check if any exposure exists before running gap detection. Show "feature not yet exposed — gap analysis unavailable" instead of false alarms.

---

### 4.12 Fraud detection — real highly-connected community flagged as fake

**Scenario:** A legitimate tight-knit team (high density, high reciprocity) looks like a fraud ring by structural metrics alone.

**Why it matters:** Density + reciprocity pattern detection has false positives on organic tight communities.

**Why you should care:** PM flags a real user group as bots. Trust and safety action against legitimate users is the worst outcome.

**Severity:** High

**What to do:** Combine structural signals with behavioral signals (account age, activity diversity, content quality). Never flag on density alone. Explanation must show which signals triggered and allow human review.

---

### 4.13 Fraud detection — sophisticated low-density ring

**Scenario:** A coordinated ring deliberately keeps density low (each account connects to only 2–3 others in the ring) to evade detection.

**Why it matters:** Density threshold misses them. Ring looks like normal users.

**Why you should care:** The fraud use case fails on the exact scenario it's meant to catch — organized, intentional manipulation.

**Severity:** Medium

**What to do:** Also check for repeated reciprocal validation patterns across contributions (Layer 4), not just relationship density. Cross-reference trust_safety_events if available.

---

## 5. Dashboard edge cases

These happen in the Dash front-end.

---

### 5.1 Clicking a node with no ego network data

**Scenario:** PM clicks a user in the ranked list, but graph builder returns an empty subgraph (orphan user, cache miss, or deleted node).

**Why it matters:** Graph panel goes blank. No error message. PM thinks the app is broken.

**Why you should care:** First impression failure. PM closes the dashboard.

**Severity:** High

**What to do:** Show "no connections found for this user" with the user's attributes from the database. Never show a blank panel silently.

---

### 5.2 Callback loop or slow callback

**Scenario:** Clicking a node triggers a callback that recomputes metrics live instead of reading cached values. Dashboard freezes for 30+ seconds.

**Why it matters:** Dash callbacks are synchronous by default. Expensive computation in a callback blocks the UI.

**Why you should care:** Every click hangs the app. Unusable demo.

**Severity:** Critical

**What to do:** All callbacks read precomputed/cached data only. Never compute centrality or community detection inside a callback.

---

### 5.3 Layer selector shows empty graph

**Scenario:** PM selects Layer 3 (user-item bipartite) expecting a node-link graph, but Layer 3 is primarily table-based per context.md.

**Why it matters:** Graph panel is empty or shows a confusing bipartite mess. PM doesn't know they're supposed to look at the table below.

**Why you should care:** Context explicitly says Layer 3 doesn't render as a standard node-link graph. If the dashboard doesn't communicate this, it looks broken.

**Severity:** Medium

**What to do:** When Layer 3 is selected, default to table view with a message: "Layer 3 is best viewed as scores and recommendations below." Optionally show a small item-user sample graph.

---

### 5.4 Most/least important toggle on exempt use cases

**Scenario:** PM toggles "least important" on onboarding flow (#6), feature discovery gap (#7), or fraud detection (#8) — which don't support this toggle.

**Why it matters:** Context exempts these three. Showing a toggle that does nothing or produces nonsense confuses the PM.

**Why you should care:** UI shows a control that doesn't work. Looks like a bug.

**Severity:** Low

**What to do:** Hide the toggle for exempt use cases. Show a brief note: "This use case uses pattern/distance detection, not importance ranking."

---

### 5.5 Search returns multiple matches

**Scenario:** PM searches "Alex" and 40 users match.

**Why it matters:** Dashboard doesn't know which Alex to show.

**Why you should care:** Search entry path — one of four entry points — becomes frustrating instead of fast.

**Severity:** Medium

**What to do:** Show a disambiguation list (name + org + key metric). PM picks the right one, then ego network loads.

---

### 5.6 Combined layer view is unreadable

**Scenario:** PM selects all 4 layers combined. Ego network shows relationship edges + activity edges + item edges + validation edges all at once.

**Why it matters:** Visual spaghetti. PM can't tell which edge type means what.

**Why you should care:** Combined view — a advertised feature — becomes the worst view instead of the most insightful.

**Severity:** Medium

**What to do:** Use distinct edge colors/styles per layer. Legend always visible. Consider defaulting combined view to aggregated (edge counts by type) rather than showing every edge.

---

### 5.7 Dashboard started before pipeline completes

**Scenario:** PM (or you) opens the dashboard before data generation, graph building, or metric caching has finished.

**Why it matters:** Dashboard reads empty database or stale cache. Everything shows zero results.

**Why you should care:** Looks like the project doesn't work when it's just a sequencing issue.

**Severity:** Medium

**What to do:** Dashboard checks for data presence on startup. Show "data not yet generated — run `make generate`" instead of empty charts.

---

## 6. PyG / Phase 2 edge cases

These apply once prediction models are added.

---

### 6.1 Train/test leakage through graph neighbors

**Scenario:** User A is in the training set, user B (connected to A) is in the test set. Model sees A's label indirectly through the graph.

**Why it matters:** Accuracy looks great but model fails on truly unseen users in production.

**Why you should care:** Phase 2 demo claims "78% accuracy" but the number is inflated. A technical reviewer will catch this.

**Severity:** Critical (Phase 2)

**What to do:** Use graph-aware splitting (cluster-based or edge-masked splits). Document split strategy.

---

### 6.2 GNN training on unrealistic synthetic structure

**Scenario:** Phase 2 starts before Phase 1 validation confirms realistic communities, skew, and influence patterns.

**Why it matters:** Context warns GNN training on unrealistic synthetic data "behaves oddly." Model may memorize artifacts of the generator rather than learning graph patterns.

**Why you should care:** You spend weeks on Phase 2 models that only work on this specific fake dataset and fail on any variation.

**Severity:** High (Phase 2)

**What to do:** Hard gate: Phase 1F must pass before Phase 2 starts. Validation report is a prerequisite.

---

### 6.3 Competing purchase/adoption models give contradictory explanations

**Scenario:** Layer 1 influence model says "friend drove adoption." Layer 3 model says "item similarity drove adoption." Layer 4 model says "curator drove adoption." Dashboard shows all three for the same user-item pair.

**Why it matters:** Context explicitly requires one combined adoption model to avoid this.

**Why you should care:** PM gets three conflicting explanations for the same event. Explainability — the core differentiator — becomes a liability.

**Severity:** High (Phase 2)

**What to do:** Single combined model with per-layer contribution breakdown in explainability panel, not separate model scores.

---

### 6.4 Model confidence is always high (overfitting)

**Scenario:** GNN achieves 99% accuracy on synthetic data because planted rules are too strong or the graph is too regular.

**Why it matters:** Overfitting to synthetic patterns. Confidence scores don't reflect real uncertainty.

**Why you should care:** Dashboard shows "99% confidence" for everything. PM treats predictions as facts. When wrong, trust collapses.

**Severity:** High (Phase 2)

**What to do:** Report accuracy on held-out clusters, not just held-out nodes. Show calibration plots. Flag if accuracy is suspiciously high.

---

### 6.5 Cold-start prediction for item with no similar items

**Scenario:** A new item belongs to a niche category with no overlapping users with existing items.

**Why it matters:** Item similarity projection is empty. Combined model has no item-side features to work with.

**Why you should care:** Cold-start — a named capability — returns "no prediction available" for the items that need it most.

**Severity:** Medium

**What to do:** Fall back to user-profile matching (Layer 3 user clustering) when item similarity is unavailable. Explanation says "prediction based on user profile, not item similarity — low confidence."

---

## 7. Cross-layer and integration edge cases

These span multiple components.

---

### 7.1 Same outcome explained by multiple graph layers

**Scenario:** A user's adoption is influenced through a friend (Layer 1), a co-play partner (Layer 2), and a followed source (Layer 4) simultaneously.

**Why it matters:** Context flags this: "which relationship actually caused this" becomes ambiguous and undermines explainability.

**Why you should care:** PM asks "why did this user adopt?" and gets three equally-weighted answers. They can't act on any of them.

**Severity:** High

**What to do:** Combined model produces one answer with per-layer contribution weights. Explanation ranks contributing layers: "Primary driver: shared activity (Layer 2, 60%). Secondary: source recommendation (Layer 4, 25%)."

---

### 7.2 Metrics and graph cache out of sync

**Scenario:** Graphs are rebuilt after a code change but metrics in `data/metrics/` are not recomputed.

**Why it matters:** Use case reads stale centrality scores that don't match the current graph. Rankings are wrong.

**Why you should care:** Silent data inconsistency. Everything looks fine but rankings are based on yesterday's graph.

**Severity:** High

**What to do:** Pipeline enforces ordering: regenerate → validate → build graphs → compute metrics → start dashboard. Timestamp checks between artifacts.

---

### 7.3 Domain config changed but data not regenerated

**Scenario:** You update `domain_config.yaml` to swap from gaming to SaaS terminology, but the database still has gaming data.

**Why it matters:** Dashboard labels say "Feature" but data still references games. Or worse, entity mappings point to columns that don't exist.

**Why you should care:** Demo for a SaaS company shows gaming data with SaaS labels. Embarrassing and confusing.

**Severity:** Medium

**What to do:** Config version/hash stored in database metadata. Dashboard warns if config hash doesn't match data hash.

> **Added edge case:** Config-data version mismatch check.
>
> **Why added:** Architecture introduces domain config but doesn't specify version tracking between config and generated data.

---

### 7.4 Scale too small for meaningful graph analysis

**Scenario:** During development, dataset is generated with 100 users instead of 10,000 for speed. Communities, centrality, and influence patterns don't emerge.

**Why it matters:** Everything "works" at small scale but results are trivial. Hubs don't exist. Communities are tiny.

**Why you should care:** You develop and test against toy data, then generate full-scale data and discover algorithms behave differently or break.

**Severity:** Medium

**What to do:** Support a `dev` scale (500 users) and `demo` scale (10,000 users) in config. Validate that dev scale still produces non-trivial structure. Run final demo on full scale.

> **Added edge case:** Dev vs demo scale modes.
>
> **Why added:** Implementation doesn't specify a development shortcut. Without one, developers may test on data too small to catch graph analysis issues.

---

### 7.5 Explainability panel missing when prediction fails

**Scenario:** PyG model returns no prediction for a node (low confidence, out of distribution). Explainability panel is blank.

**Why it matters:** Context requires every alert/prediction to include explanation + recommended action. A blank panel violates the core design principle.

**Why you should care:** PM sees a flagged user with no explanation. The tool's main differentiator — transparency — fails exactly when the model is uncertain.

**Severity:** High

**What to do:** When prediction unavailable, show structural explanation from NetworkX (Phase 1 fallback) with note: "Prediction unavailable — showing structural analysis only."

---

## 9. Environment configuration edge cases

This project uses no external APIs. These edge cases apply to local `.env` and path configuration only.

---

### 9.1 Wrong database path in `.env`

**Scenario:** `DATABASE_PATH` points to a non-existent folder or read-only location.

**Why it matters:** Generator or dashboard fails on first write with opaque SQLite error.

**Why you should care:** Works on one machine where path exists; fails for everyone else.

**Severity:** High

**What to do:** `check_env.py` validates paths exist and are writable. Document defaults in `.env.example`.

---

### 9.2 `.env` not copied from example

**Scenario:** Developer clones repo but never copies `.env.example` to `.env`.

**Why it matters:** App falls back to wrong defaults or crashes on missing vars.

**Why you should care:** README must say "copy `.env.example` → `.env`" as first setup step.

**Severity:** Medium

**What to do:** `check_env.py` fails fast with clear message listing missing vars.

---

### 9.3 `.env` committed to git

**Scenario:** Local `.env` accidentally tracked in version control.

**Why it matters:** Machine-specific paths leak; future secrets could leak if added later.

**Why you should care:** Portfolio repos should never track local config.

**Severity:** Medium

**What to do:** `.gitignore` includes `.env`. Phase 1G runbook runs `git ls-files .env` (BUG-11.02).

---

## 8. Quick reference — edge cases by severity

### Critical (fix before demo)

| # | Edge case | Layer |
|---|---|---|
| 1.1 | Flat uniform data | Data generation |
| 1.2 | Impossible timestamps | Data generation |
| 1.8 | Planted rules leaked to model | Data generation / PyG |
| 2.2 | Invalid node references | Graph building |
| 3.1 | Betweenness computed live (slow) | Analytics |
| 5.2 | Expensive computation in Dash callback | Dashboard |
| 6.1 | Train/test leakage through neighbors | PyG |

### High (will undermine demo quality)

| # | Edge case | Layer |
|---|---|---|
| 1.4 | Super-hubs dominate | Data generation |
| 1.6 | Activity graph = relationship graph | Data generation |
| 1.7 | Influence too strong/weak | Data generation |
| 2.1 | Disconnected components | Graph building |
| 2.4 | Weighted vs unweighted confusion | Graph building |
| 2.6 | Ego network too large | Graph building |
| 2.7 | Stale graph cache | Graph building |
| 3.2 | Zero/NaN eigenvector scores | Analytics |
| 3.3 | One giant community | Analytics |
| 3.6 | Metrics on wrong layer | Analytics |
| 4.3 | Weak = strong contamination alert | Use case |
| 4.4 | Already-churned user flagged | Use case |
| 4.6 | Rollout to hubs kills measurement | Use case |
| 4.7 | Popularity vs validated influence | Use case |
| 4.10 | Global exposure hides local gaps | Use case |
| 4.12 | Real community flagged as fraud | Use case |
| 5.1 | Empty ego network, no message | Dashboard |
| 6.3 | Competing adoption models | PyG |
| 7.1 | Same outcome, multiple layer explanations | Cross-layer |
| 7.2 | Metrics/graph cache out of sync | Cross-layer |

---

## Flagged additions in this document

These edge cases were not explicitly listed in context.md, architecture.md, or implementation.md:

| # | Edge case | Why it was added |
|---|---|---|
| A | Ego network size cap with truncation message (2.6) | Context says filtered views but not max size |
| B | Rollout strategy modes: spread vs measurement (4.6) | Context uses eigenvector for rollout but doesn't address measurement tradeoff |
| C | Active vs inactive connection for onboarding (4.9) | Context defines binary connection check but not stale connections |
| D | Config-data version mismatch check (7.3) | Domain config introduced in architecture but no version tracking specified |
| E | Dev vs demo scale modes (7.4) | No development shortcut scale defined in implementation |
| F | Wrong `.env` paths / missing local config (§9) | Local-only project; covered in bugs.md and evals.md |

Review these and remove or adjust any that don't fit your priorities.
