# Slack Product Teardown — Network Graph Intelligence Project

## Core Concept

A product teardown of Slack using network graph analysis, built as a synthetic-data prototype rather than a conceptual essay. The goal is to show how understanding user/workspace network structure can power real product team decisions (experimentation, rollout, retention, risk).

Chosen over Substack because Slack's graph *is* the product — workspaces, channels, DMs, mentions, and Slack Connect are structural to how the product functions, not just a growth layer on top of it. This gives more depth across multiple decision-making angles (A/B contamination, rollout sequencing, blast-radius risk, viral targeting, novelty confounds) rather than just one or two.

---

## Locked-In Decisions

### 1. Data approach: Synthetic dataset
Slack doesn't expose real usage graphs publicly, so the project will simulate synthetic workspace data — same approach as the Turkey dataset project (K-means customer segmentation seeding). This produces an actual working prototype/artifact rather than an argument-only teardown.

### 2. Scope: Multiple workspaces
The synthetic dataset will simulate **multiple companies' workspaces**, not just one deep internal workspace. This is specifically to surface cross-workspace effects — Slack Connect-style shared channels between companies, cross-company expansion patterns, and inter-workspace bridges — which a single-workspace simulation wouldn't show.

### 3. Prototype form: Dashboard
The end deliverable is a dashboard that visualizes the network and its insights. The specific decision-making use case the dashboard centers on (A/B contamination detection, super-connector churn risk, rollout sequencing, or a combination) is intentionally **not locked yet** — to be decided during a dedicated ideation session once the data/graph foundation exists and it's clearer what the graph actually reveals.

---

## Candidate Use Cases to Ideate On Later

(Not yet chosen — options to revisit)

- **A/B test contamination detection** — flagging when a test/control split crosses a real connection (e.g. same workspace or shared channel), which violates the independence assumption behind standard A/B testing. Refined: node should be classified by connection strength/influence, raising an alert when a strongly-connected node is placed in the variant group, with recommended exclusions based on that node's connection strength.
- **Champion / super-connector churn risk** — identifying structurally central users whose departure would risk cascading churn through their cluster
- **Feature rollout sequencing** — using network position to decide which users/workspaces to roll a feature out to first for maximum organic exposure and fastest real-world signal
- **User research prioritization (community-validated influence)** — identifying which nodes are the strongest candidates to feed user research, based not on raw connectivity alone but on whether a node's feedback/participation gets validated by connected nodes (i.e., a node whose contributions other users appreciate/engage with is a stronger signal source than a highly-connected node whose output isn't validated by its cluster). Extension of the community participation influence mechanism already scoped in the friends-graph layer, applied to a new decision (who to prioritize for research) rather than a new mechanism.
- **Support/moderation escalation prioritization** — flagging when a bug report or complaint originates from a highly-central node, since the negative experience is more likely to propagate through their cluster than the same issue from a peripheral node. Helps prioritize fixes by blast radius, not just severity.
- **Onboarding flow decisioning** — using existing network signals (whether a new user already has a connection on the platform) to decide whether they need a guided onboarding flow or can go self-serve, since users entering with an existing connection tend to ramp faster.
- **Feature discovery gap detection** — identifying clusters structurally isolated from where a feature/content is organically spreading, to catch under-exposed segments before concluding a feature underperformed, when it may simply not have reached that part of the graph yet.
- **Fraud/fake-account ring detection** — identifying clusters with unusually dense, reciprocal, or symmetric structure that doesn't resemble organic behavior (bot networks, fake engagement rings) — a product integrity/trust & safety use case.
- **All of the above, at a basic level** — a broader dashboard touching each use case lightly rather than going deep on one

---

## The Differentiation Angle — Why This Isn't "What Internal Teams Already Do"

"I built the same thing internal teams already have" is a weak pitch. "I built something that reveals what internal teams typically can't see, or presents it in a way they don't" is a strong one.

Four real gaps in how internal graph analysis typically works at companies:

1. **Most internal graph analysis stays inside data science — it never reaches the PM's desk in a usable form.** Growth/data teams often compute this, but it lives in a notebook or a quarterly report, not a live tool a PM can query before making a rollout decision. Differentiator: not the analysis itself, but making it a self-serve decision tool a PM opens *before* shipping a feature, not after reading a retrospective.

2. **Companies use the graph for retention/expansion — rarely for experimentation design.** The A/B contamination angle is the one almost nobody operationalizes, because it requires connecting the growth team's graph data to the experimentation team's test infrastructure — and those are usually different teams, different tools, sitting in different parts of the org. A dashboard that says "don't run this test the way you're about to, here's why, here's the contaminated pairs" *before* a test launches is a genuinely different artifact than what exists at most companies, because it requires connecting two systems that are typically siloed.

3. **Most internal tools show the graph after the fact, not as a forward simulation.** "Here's what happened" vs. "here's what will likely happen if you roll this out to these 5% of users vs. these other 5%." A forward-looking rollout simulator — pick your rollout cohort, see the predicted exposure/blast-radius before you ship — is a meaningfully different product than a retrospective dashboard.

4. **The transparency angle itself is the differentiator.** Internal tools are black boxes to everyone except the data team that built them — a VP doesn't see *why* a user is flagged high-risk, just a score. A dashboard that shows its reasoning (this cluster, this centrality score, this is why we're flagging it) in a way a non-technical stakeholder can actually interrogate is a real, defensible difference — explainability as the product, not just the score.

**Leading candidate: #2 (experimentation contamination)** — it's the least commonly solved, it's concrete, and it directly ties back to something every product team does constantly (run A/B tests) and usually gets subtly wrong without knowing it.

---

## Technical Architecture — NetworkX + PyG in Tandem

The plan is to use NetworkX and PyG together, each doing a distinct job, rather than relying on just one library.

### NetworkX's job — structure and explainability

Fast to reason with and easy to explain to a non-technical stakeholder, which matters for the explainability differentiator (#4 above):
- **Centrality measures** — who's structurally critical (betweenness centrality for "who bridges clusters," eigenvector centrality for "who's connected to other important people")
- **Community detection** — Louvain or similar, finding the actual clusters/teams
- **Shortest-path and connectivity analysis** — how isolated is this user if their champion leaves

This is the **descriptive layer** — what the graph looks like right now. Inherently visual and interpretable, which is what makes it PM-legible without a data science background.

### PyG's job — prediction, the part NetworkX can't do

NetworkX tells you what the graph looks like today. PyG trains a model *on* the graph to predict what happens next:
- **Link prediction** — will these two users/workspaces connect soon (powers rollout/expansion forecasting)
- **Node classification with network context** — predict churn risk where the model factors in a user's neighbors' behavior, not just their own (the "social risk" upgrade over a normal churn classifier)
- **GNN-based influence propagation** — simulate "if this user churns, here's the predicted cascade through their cluster" as an actual forward simulation, not a retrospective count

This is the **predictive layer** — the piece that turns the dashboard from "here's what happened" into "here's what will likely happen if you do X," which is the sharpest differentiation angle (a forward simulator, not a retrospective report).

### Why using both, deliberately, is worth stating explicitly in the writeup

Most people would reach for just one. NetworkX alone gives insight but no prediction. PyG alone gives predictions but a black-box model a PM can't interrogate. Using NetworkX for the transparent structural layer and PyG for the predictive layer — and being explicit about *why* each tool is doing a different job — is a real architecture decision, not a "used two libraries" flex. It directly supports the explainability differentiator: NetworkX shows *why* someone is flagged, PyG shows *what's predicted to happen*, and a PM gets both instead of one opaque score.

### Sequencing note

PyG (GNN training) is a meaningfully heavier lift than NetworkX — it needs labeled examples (or a simulation that generates plausible ground truth) to train against, and GNN training on a synthetic dataset can behave oddly if the synthetic data doesn't have enough realistic structure baked in. Recommended order: build the NetworkX layer first, get the dashboard's descriptive half working end-to-end, and add PyG as the second phase once the graph itself is confirmed realistic enough to predict on.

---

## Layer 1: Friends/Social Graph — Scoping Q&A

Starting build sequence with the friends/social graph layer. Below are the specific capabilities scoped, with status/mechanism notes.

Since all data is synthetic, nothing here is blocked by data availability — the constraint is design (what rule you bake into the generator), not access.

1. **Which friend joined first / later** — Trivial. Attribute-level (`join_date` timestamp per node). No graph logic required.

2. **Do connected friends play the same games** — Trivial. User-game bipartite layer overlaid on the friend graph; check game-list overlap between connected nodes.

3. **Referral tracking (did one friend bring the other, external or internal)** — Not a graph-detection task, and not a PyG task. Must be encoded as ground-truth metadata at generation time (`referred_by`, `referral_source`). Cannot be inferred after the fact from timing/connection alone without it being a weaker, non-defensible claim.

4. **Purchase influence (who purchases more; does one node's purchase influence a connected node's purchase)** — Two parts: purchase count is trivial (just a number). Influence requires a simulation rule planted at generation time (e.g., A's purchase raises B's purchase probability within a window). This is the layer PyG applies to — specifically, node classification with network context — but only if the planted rule is withheld from the model and it must recover/predict the pattern from graph structure and behavior data alone. If the rule is fed to the model directly, there's nothing for PyG to demonstrate.

5. **Community participation influence (does one node's participation drive connected nodes' participation)** — Same pattern as #4: requires a planted propagation rule at generation time; PyG's job afterward is to recover/predict it from structure, not be told it.

6. **Node's influence on friends vs. non-friends** — Possible, but needs explicit definition first. Non-friends have no edge, so there's no direct graph path for "influence" to travel through — this would be measured as connected-pair correlation vs. a random-pair baseline/control group, not influence through the graph itself. Not yet defined precisely.

7. **Playtime influence (does one node's playtime influence a connected node's playtime)** — Same pattern as #4/#5: planted propagation rule at generation time, PyG recovers/predicts it afterward.

**Cross-cutting note:** Items 3, 4, 5, and 7 share the same underlying pattern — the "influence" isn't discovered from organic behavior, it's encoded into the synthetic generator and then the graph/PyG layer is used to verify it can be recovered. This is a legitimate way to validate the mechanism works, but it's a validation of simulation design, not a genuine independent finding. To be stated explicitly in any writeup so it doesn't read as an emergent discovery.

**PyG applicability specifically:** Of the above, PyG (node classification with network context) applies to 4, 5, and 7 — and only for the prediction/recovery step, not the generation step. Item 3 (referral) is pure ground-truth metadata with nothing to predict — PyG has no role there.

---

## Layer 2: Co-Play Graph — Potential Applications

Co-play graph = users connected by playing games together (multiplayer sessions), distinct from and stronger than the friend-list edge type. Each application below is tagged with the library it relies on.

1. **Stronger friend-recommendation signal** — flagging non-friend pairs with high co-play frequency as high-confidence friend suggestions. **NetworkX** (edge weight/frequency analysis on the co-play graph; descriptive, no prediction needed).

2. **Community/squad detection** — running community detection on co-play edges to surface actual play groups, compared against the stated friends list. **NetworkX** (Louvain community detection — descriptive/structural).

3. **Churn risk via squad dependency** — a user's engagement risk rising when their primary co-play partner(s) stop playing. **PyG** (node classification with network context — this is a predictive claim about future behavior based on neighbor state, and per the cross-cutting note below, requires a planted propagation rule to validate against).

4. **Matchmaking/session quality** — surfacing preferred play partners for matchmaking or "invite back" prompts. **NetworkX** (edge weight/frequency — descriptive; no prediction required, just surfacing existing structure).

5. **Viral game adoption/expansion** — predicting whether a user will adopt a new game because their co-play group adopted it. **PyG** (link prediction / node classification — this is a forward prediction, same influence-propagation pattern as friend-graph items 4/5/7).

6. **Toxicity/positive-behavior clustering** — detecting clusters with consistently high reports/bans vs. high positive engagement. **NetworkX** for the clustering itself (community detection); **PyG** if extended to *predict* which cluster a new/borderline user will trend toward based on neighbor behavior.

7. **Bridge/cross-group detection** — identifying users who regularly play across multiple otherwise-separate groups. **NetworkX** (betweenness centrality — descriptive, structural).

8. **A/B contamination in co-play sessions** — flagging when test/control split crosses an active co-play session, violating independence assumptions. **NetworkX** (structural/descriptive — same logic as the Slack A/B contamination use case; this is detection of an existing structural condition, not a prediction, so PyG isn't needed).

**Cross-cutting note (same as friends-graph):** Items 3, 5, and the predictive extension of 6 rely on a planted influence/propagation rule at data-generation time, which PyG then recovers/predicts — not an organic discovery. Keep this same distinction in mind here as noted in Layer 1.

**Flag:** if both the friends graph and co-play graph carry overlapping influence mechanics (e.g., both claim to explain the same purchase or engagement outcome), the two edge types need to stay clearly separable in the data model — otherwise "which relationship actually caused this" becomes ambiguous and undermines the explainability differentiator the project is built around.

---

## Layer 3: User–Game Bipartite Graph — Potential Applications

Users connected to the games they own/play — powers "people who play X also play Y" recommendation logic (same as Amazon's "bought together"). Each application tagged with the library it relies on.

1. **"People who play X also play Y" recommendations** — core collaborative filtering use case. **NetworkX** for co-occurrence/projection (game-game graph via shared users); **PyG** if upgraded to link prediction for learned, personalized recommendations.

2. **Game similarity clustering** — grouping games by shared-player overlap into implicit taste/genre clusters. **NetworkX** (community detection on game-game projection).

3. **User taste-profile clustering** — grouping users by overlapping ownership into taste segments. **NetworkX** (community detection on user-user projection).

4. **Cold-start recommendation for new games** — predicting which existing users are likely to pick up a new release based on similarity to games they already own. **PyG** (link prediction).

5. **Bundle/cross-sell optimization** — identifying frequently co-owned game pairs/groups for bundle pricing or storefront placement. **NetworkX** (edge weight analysis — descriptive).

6. **Publisher portfolio cannibalization/synergy detection** — checking whether same-publisher games are typically co-owned or mutually exclusive. **NetworkX** (structural/descriptive).

7. **Purchase-influence prediction with combined context** — predicting whether a user will buy a new game using both social graph (friends/co-play) and existing game-ownership profile as combined input. **PyG** (node classification with network context).

### Decision: Items 4, 5, and 7 to work together

Cold-start recommendation (4), bundle/cross-sell optimization (5), and purchase-influence prediction (7) are to be combined rather than treated as separate mechanisms. This also connects to the overlap flagged earlier — item 7 here is the same underlying purchase-prediction question as friends-graph item 4 and co-play-graph item 5, so the combined model is expected to fold in social-graph signal (friends/co-play) alongside bipartite ownership signal, rather than running three competing purchase-prediction mechanisms independently. Exact mechanics of how 4, 5, and 7 combine (e.g., shared feature set, single model vs. pipeline of models) not yet defined — to be worked out during build.

---

## Layer 4: Review/Influence Graph — Potential Applications

Users connected via review helpfulness votes, and users connected to curators they follow. Two distinct sub-structures bundled under one label — kept together here for scoping, library/edge-type separation to be finalized during build.

1. **Trusted reviewer identification** — surfacing users whose reviews consistently get marked helpful, weighted by voter trust rather than raw count. **NetworkX** (eigenvector/PageRank-style centrality on the helpfulness-vote graph).

2. **Influential curator identification** — surfacing curators with the largest, most engaged follower base. **NetworkX** (degree/eigenvector centrality on the curator-follow bipartite graph).

3. **Review credibility weighting for storefront display** — ranking reviews by reviewer centrality score rather than raw helpfulness count. **NetworkX** (direct application of #1's output — descriptive, no prediction).

4. **Curator recommendation → purchase influence** — predicting whether a user buys a game because a curator they follow recommended it. **PyG** (link prediction / node classification).

5. **Reviewer → purchase influence** — predicting whether a user buys/plays a game because a trusted reviewer (per #1) reviewed it positively. **PyG** (node classification with network context).

6. **Review-bombing / coordinated vote-brigading detection** — identifying clusters of accounts voting-helpful each other's reviews in unusually dense, reciprocal patterns. **NetworkX** (community detection + reciprocity/density analysis — structural/descriptive).

7. **Curator authenticity/quality scoring** — checking whether curator recommendations correlate with follower purchase/rating behavior. **NetworkX** for the correlation/overlap check (descriptive); **PyG** if extended into a predictive quality score.

8. **Influence-network bridge detection** — identifying reviewers/curators bridging otherwise-separate taste clusters. **NetworkX** (betweenness centrality — structural/descriptive).

**Flag carried forward:** items 4 and 5 are the fourth and fifth instances of a "does X influence purchase" claim across the graph layers scoped so far (friends, co-play, bipartite, review/influence). Given the Layer 3 decision to combine items 4/5/7 there, these two items are strong candidates to fold into that same combined purchase-prediction model rather than becoming standalone mechanisms. Not yet decided — flagged for a future call, same as the Layer 3 decision was.

---

## Schema Structure

Scope: all 4 graph layers, all candidate use cases (per decision to build for full scope, not a narrowed v1). Table-name level; column-level detail and exact relationships (foreign keys, directed vs undirected edges, computed vs stored projections) to be worked out next.

### Core entity tables
- `users` — user_id, join_date, workspace/company_id, other base attributes
- `games` — game_id, title, developer, publisher, genre_tags, release_date
- `curators` — curator_id, name, follower_count (or derived)
- `workspaces` / `companies` — multi-entity structure carried over from original multi-workspace concept

### Layer 1 — Friends/Social graph
- `friend_edges` — user_id_a, user_id_b, connection_date (directed/undirected TBD)
- `referrals` — referred_user_id, referrer_user_id, referral_source (internal/external), timestamp — ground-truth metadata

### Layer 2 — Co-play graph
- `coplay_sessions` — session_id, game_id, timestamp, duration
- `coplay_session_participants` — session_id, user_id (join table)
- Derived: `coplay_edges` — user_id_a, user_id_b, frequency, total_shared_playtime (computed vs. stored TBD)

### Layer 3 — User–game bipartite graph
- `user_game_ownership` — user_id, game_id, purchase_date, playtime_total
- Derived: `game_game_projection` — game_id_a, game_id_b, shared_owner_count (likely computed rather than stored)

### Layer 4 — Review/influence graph
- `reviews` — review_id, user_id, game_id, review_text/rating, timestamp
- `review_helpfulness_votes` — voter_user_id, review_id, timestamp (directed edge)
- `curator_follows` — user_id, curator_id, follow_date
- `curator_recommendations` — curator_id, game_id, recommendation_date

### Supporting tables for use cases
- `community_posts` / `community_participation` — user_id, post_id, timestamp, engagement_received (community-participation-influence mechanism; UX research use case)
- `support_tickets` / `bug_reports` — user_id, ticket_id, timestamp, severity (support/moderation escalation)
- `feature_exposure_log` — user_id, feature_id, exposed_flag, timestamp, variant/control (A/B contamination detection; rollout sequencing)
- `churn_events` — user_id, churn_date or last_active_date (churn risk)
- `onboarding_events` — user_id, onboarding_flow_type, completion_status (onboarding flow decisioning)

### Ground-truth / simulation control tables
- `planted_influence_rules` — record of which propagation rules were baked into the synthetic generator and their parameters, kept separate from the main dataset so PyG's recovery of them can be validated against known ground truth

---

## Data Generation Scale

Locked-in row-count targets, sized for realism vs. compute tractability (betweenness centrality and GNN training runnable without needing to sample down further at this scale).

### Core entities
- `users`: **10,000**
- `games`: **1,000**
- `curators`: **300**

### Relationship/edge tables
- `friend_edges`: average degree 8–20 → **80,000–200,000 edges**, power-law skew required (most users 5–10 friends, hub minority 50–100+).
- `coplay_sessions`: ~20–50 sessions per active user over the simulation window → **200,000–500,000 session records**, with `coplay_session_participants` at 2–8 rows per session.
- `user_game_ownership`: average 15–40 games/user → **150,000–400,000 rows**.
- `reviews`: 5–10% of ownership rows → **8,000–40,000 reviews**.
- `review_helpfulness_votes`: skewed toward a minority of reviews → **20,000–60,000 vote rows**.
- `curator_follows`: average 3–8 curators followed per user → **30,000–80,000 rows**, implying ~100–270 followers/curator on average (power-law skew still required across the 300 curators).
- `curator_recommendations`: scales with curator activity, not users → **6,000–30,000 rows**.

**Note:** Row counts alone don't guarantee analytical validity — distribution shape (power-law skew across friend edges, ownership, curator follows) matters more than volume. Flat/uniform random generation would produce technically valid but analytically meaningless results (centrality scores converging to the same value, arbitrary-looking communities, no real structure for PyG to learn from).

---

## Data Generation Rules

### 1. Users — attributes and timing
- `join_date`: spread over a defined simulation window (e.g., 3 years) following a growth-curve pattern (slow start, acceleration, plateau) rather than uniform random.
- Each user gets a hidden "activity propensity" score (e.g., lognormal) at creation, driving friend count, ownership count, review frequency, etc., so behaviors correlate realistically across tables rather than being independently randomized.

### 2. Friend edges — power-law degree distribution
- Preferential-attachment-style generation (Barabási–Albert-like) rather than pure random pairing, producing the hub/peripheral skew centrality measures depend on.
- `connection_date` must be ≥ both users' `join_date`.

### 3. Co-play sessions
- 70–80% of sessions drawn from existing friend graph, remainder random/matchmade strangers — this gap is what differentiates the co-play graph from the friend graph.
- Session `game_id` correlated with participants' existing genre/taste cluster, not uniform random across all games.

### 4. User–game ownership
- Each game gets a hidden "popularity" score (lognormal/power-law) — blockbusters owned by thousands, niche titles by dozens.
- Ownership probability weighted by both popularity and the user's hidden taste-cluster match, not popularity alone — required for genre/taste clustering (Layer 3 items 1–3) to produce meaningful results.

### 5. Reviews and helpfulness votes
- Review probability scales with user activity propensity.
- Each review gets a hidden "quality" score; votes are power-law distributed toward high-quality reviews, and preferentially sourced from users connected to the reviewer (friend/co-play graph or shared game ownership) rather than random strangers — required for "trusted reviewer" centrality to be meaningful.

### 6. Curator follows and recommendations
- Curator follower counts power-law/Zipf distributed across the 300 curators.
- Each curator gets a taste-cluster/specialization; recommendations align with it — required for curator-authenticity scoring (Layer 4 item 7) to have real signal.

### 7. Planted influence/propagation rules
Decision: **5 distinct influence types** — purchase, community participation, playtime, curator, reviewer — sharing one common rule engine/parameter format rather than being hand-built per layer, so the combined purchase-prediction model (Layer 3 items 4/5/7 + Layer 4 items 4/5) has a coherent signal to learn from.

Each rule to define: trigger event, probability/effect boost applied to connected nodes, decay window, and which edge type(s) it propagates across.

All planted rules and parameters stored in `planted_influence_rules` (schema) so PyG's later recovery of the pattern can be validated against known ground truth. Effect size should be moderate and deliberately tunable — too strong makes PyG's detection trivial, too weak makes it indistinguishable from noise.

### 8. Time-based consistency
All event timestamps (purchase, review, coplay session, vote, follow) must respect causal order relative to `join_date` and `friend_edges.connection_date` (no reviewing before owning, no co-play before both users joined, etc.). To be checked with a validation pass after generation, not just enforced at generation time.

---

## Visual / Dashboard Design

### Network rendering approach
Full raw graph rendering at locked scale (10,000 users, 80,000–200,000+ edges) is not viable — well past what force-directed layouts can render meaningfully. Decision: **filtered views only** — no default full-graph render.

### Entry points into filtered node views
PM has flexibility to choose among four entry paths (not funneled into one):
1. **Ranked list entry** — sortable/filterable table of nodes ranked by centrality score. Metrics: **betweenness centrality** and **eigenvector centrality**. Clicking a row opens that node's filtered ego-network view.
2. **Alert-driven entry** — system proactively surfaces flagged nodes (e.g., A/B contamination risk, support escalation) with the filtered graph view attached directly to the alert.
3. **Search/lookup entry** — PM searches by user ID/name directly to land on a specific node's ego-network view.
4. **Cluster drill-down entry** — PM starts at aggregated cluster-level view (community bubbles), drills into a cluster, then sees top-ranked/most-central nodes within it as a sub-list before reaching an individual node.

### Layer selection
- PM can view **Layer 1, 2, 3, or 4 individually**
- **Combined view**: all 4 layers together
- **Custom view**: PM selects any subset of layers

### Handling non-graph-native output (Layer 3 and similar)
Layers 1/2/4 are graph/node-centric (ego-network views render naturally). Layer 3 (user–game bipartite) is primarily score/table-based (game-game similarity, purchase-likelihood) and doesn't render as a node-level network in the same way. Resolution: within any layer view, the PM can **scroll down** to separate information blocks — non-graph-native output (like Layer 3's scores/tables, or the combined purchase-prediction score's per-layer breakdown) lives below the graph rendering as its own section rather than being force-fit into the network visualization.

### Use case section
The 8 candidate use cases form a **separate top-level section** from the layer views. For each use case, the PM can toggle between **"view most important nodes"** and **"view least important nodes."**

**Metric definitions per use case (locked):**
1. **A/B contamination** — connection strength / influence strength
2. **Champion/super-connector churn risk** — combination: eigenvector centrality + engagement/activity signal (exact weighting TBD at build)
3. **Feature rollout sequencing** — eigenvector centrality
4. **User research prioritization** — community-validated influence (feedback validated by connected nodes, not raw connectivity)
5. **Support/moderation escalation** — betweenness centrality
6. **Onboarding flow decisioning** — binary (has existing connection on platform or not) — **exempted from most/least-important toggle**, doesn't fit the ranking framing
7. **Feature discovery gap detection** — isolation/distance from exposure — **exempted from toggle**, distance-based rather than importance-based
8. **Fraud/fake-account ring detection** — density/reciprocity pattern — **exempted from toggle**, pattern-based rather than importance-based

---

## Why This Project Matters (Portfolio Framing)

This reframes retention/experimentation thinking from "who is likely to churn" or "did the test win" to a systems-level question: how does the *structure* of connections between users change what a product team should do. It's a genuinely underused lens — most tooling defaults to treating users as independent rows in a table — and using synthetic data still lets the prototype prove the mechanism convincingly without needing access to Slack's real internal data.
