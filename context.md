# Network Graph Intelligence Project

## Core Concept

Build a generic network graph intelligence system that can be adapted to any company or connected product. It is not a Slack-specific teardown. The system models users, organizations, items, activities, and influence relationships so product teams can understand how network structure should affect experimentation, rollout, retention, recommendations, research, support, onboarding, and trust-and-safety decisions.

The project should be a working prototype built on synthetic data, not a conceptual essay. Its output is a decision-support dashboard that makes graph analysis understandable and actionable for product managers and other non-technical stakeholders.

The domain model is configurable. Terms such as games, co-play, reviews, curators, workspaces, and companies are concrete examples of generic concepts such as items, shared activities, contributions, trusted sources, and organizations. A company should be able to substitute its own entities and events without changing the core analytical approach.

---

## Chosen Use Cases

1. **A/B test contamination detection** — flag when a test/control split crosses a meaningful connection and violates the independence assumption behind standard A/B testing. Nodes should be evaluated by connection or influence strength. The system should raise an alert when a strongly connected node is assigned to the variant group and recommend exclusions or cohort changes.
2. **Champion / super-connector churn risk** — identify structurally central users whose departure could cause cascading churn or disengagement within their cluster.
3. **Feature rollout sequencing** — use network position to decide which users, teams, or organizations should receive a feature first for maximum organic exposure and fast real-world signal.
4. **User research prioritization through community-validated influence** — identify the strongest research participants based not only on connectivity, but also on whether connected users validate or engage with their contributions.
5. **Support/moderation escalation prioritization** — flag bugs or complaints from highly central users because their negative experience may propagate farther through the network. Prioritize by likely blast radius as well as severity.
6. **Onboarding flow decisioning** — use existing-network signals, such as whether a new user already knows or interacts with someone on the platform, to determine whether guided onboarding or self-service onboarding is more appropriate.
7. **Feature discovery gap detection** — identify clusters that are structurally isolated from the organic spread of a feature or piece of content, preventing a team from mistaking lack of exposure for poor product performance.
8. **Fraud/fake-account ring detection** — identify clusters with unusually dense, reciprocal, or symmetric relationships that do not resemble organic behavior, including bot networks and fake-engagement rings.

---

## Technical Architecture — NetworkX + PyG in Tandem

NetworkX and PyTorch Geometric (PyG) have separate responsibilities and should be used together.

### NetworkX — structure and explainability

NetworkX provides the descriptive and interpretable layer:

- **Centrality measures** — identify structurally critical nodes. Betweenness centrality finds bridges between clusters; eigenvector centrality identifies nodes connected to other important nodes.
- **Community detection** — use Louvain or a similar method to find real clusters, teams, or behavioral communities.
- **Shortest-path and connectivity analysis** — measure isolation, dependency, and how connectivity changes when a key node leaves.
- **Edge strength, density, and reciprocity** — support relationship scoring, contamination detection, recommendation signals, and suspicious-cluster detection.

This layer explains what the graph looks like now and why a person, cluster, or relationship has been flagged.

### PyG — prediction

PyG trains models on graph structure and behavior to predict what may happen next:

- **Link prediction** — predict which users, organizations, or user-item pairs are likely to connect.
- **Node classification with network context** — predict outcomes such as churn, adoption, or risk using both a node's behavior and its neighbors' behavior.
- **GNN-based influence propagation** — simulate likely cascades after churn, adoption, participation, or another trigger.

This is the predictive layer that supports forward-looking decisions and scenario simulation.

### Why both are needed

NetworkX alone provides interpretable insights but not learned predictions. PyG can provide predictions, but those predictions may be difficult for a product manager to interrogate. Together, NetworkX shows why something is structurally important and PyG estimates what is likely to happen. The dashboard should expose both the prediction and its supporting graph context rather than presenting only an opaque score.

### Recommended build sequence

Build the NetworkX descriptive layer and dashboard first. Add PyG after the graph generator produces realistic, validated structure. GNN training needs labeled examples or plausible synthetic ground truth, and it will not be meaningful if the generated graph lacks realistic communities, skew, and behavioral relationships.

---

## Layer 1: User Relationship / Social Graph

This layer represents explicit relationships between users, such as friendship, following, collaboration, membership, or another company-specific connection.

1. **Which connected user joined first or later** — store a `join_date` timestamp on each user. This is attribute-level logic and does not require graph inference.
2. **Whether connected users interact with the same items** — overlay a user-item bipartite layer and calculate item overlap between connected nodes.
3. **Referral tracking** — store `referred_by` and `referral_source` as ground-truth metadata during generation. Referral cannot be defensibly inferred from connection timing alone.
4. **Purchase or conversion influence** — separate the raw outcome count from the influence claim. Influence requires a planted simulation rule, such as one user's conversion increasing a connected user's conversion probability within a time window. PyG should attempt to recover the pattern without receiving the planted rule as an input.
5. **Community participation influence** — use the same planted-propagation pattern to test whether one user's participation affects connected users' participation.
6. **Influence on connected versus unconnected users** — compare connected-pair correlation with a random-pair baseline. Because unconnected users have no direct edge, this is a control-group comparison rather than direct graph propagation.
7. **Activity-level influence** — test whether one node's usage or engagement affects a connected node's usage or engagement, again using a planted rule and a recovery step.

Referral is ground-truth metadata. Conversion, participation, and activity influence use the same general mechanism: the synthetic generator plants a causal pattern, and the graph/model layer tests whether that pattern can be recovered. The write-up must clearly state that this validates the simulation and analytical mechanism; it is not an independent causal discovery from real-world data.

PyG applies to the prediction/recovery step for conversion, participation, and activity influence. It does not generate those effects and has no role in simple referral metadata.

---

## Layer 2: Shared Activity Graph

This layer connects users who participate in the same meaningful activity. Depending on the company, this could mean playing together, collaborating on a document, attending the same session, joining a transaction, participating in a project, or another shared event. It is distinct from and often stronger than an explicit social edge.

1. **Stronger connection recommendation signal** — identify non-connected pairs with high shared-activity frequency as high-confidence connection suggestions. Use NetworkX edge-weight and frequency analysis.
2. **Community/group detection** — run community detection on shared-activity edges and compare actual behavior groups with declared relationships.
3. **Churn risk through group dependency** — predict whether a user's engagement risk rises when their primary activity partners stop participating. Use PyG node classification with a planted propagation rule.
4. **Session or collaboration quality** — surface preferred activity partners for matching, invitations, or re-engagement prompts. Use NetworkX edge strength and frequency.
5. **Viral item or feature adoption** — predict whether a user will adopt an item or feature after their activity group adopts it. Use PyG link prediction or node classification.
6. **Negative/positive behavior clustering** — detect communities with consistently high reports, policy violations, or positive engagement. Use NetworkX for clustering and PyG only when predicting the likely trajectory of a new or borderline user.
7. **Bridge/cross-group detection** — identify users who regularly participate across otherwise separate groups. Use NetworkX betweenness centrality.
8. **A/B contamination in shared activities** — flag test/control assignments that cross an active shared event. This is structural detection with NetworkX, not a prediction problem.

Predictive outcomes in this layer rely on planted influence rules. Explicit social edges and shared-activity edges must remain separate in the data model so the dashboard can explain which relationship contributes to an outcome.

---

## Layer 3: User–Item Bipartite Graph

This layer connects users to the products, content, features, services, games, or other items they own, use, consume, or engage with.

1. **"People who use X also use Y" recommendations** — use NetworkX co-occurrence and projection to create an item-item graph through shared users. PyG can extend this into learned personalized link prediction.
2. **Item similarity clustering** — group items by shared-user overlap into implicit category, need, or taste clusters using community detection on the item-item projection.
3. **User profile clustering** — group users by overlapping item use or ownership using community detection on a user-user projection.
4. **Cold-start recommendation for new items** — predict which existing users are likely to adopt a new item based on similarity to items they already use. Use PyG link prediction.
5. **Bundle/cross-sell optimization** — identify frequently co-used or co-owned item groups for packaging, placement, or pricing decisions. Use NetworkX edge-weight analysis.
6. **Portfolio cannibalization/synergy detection** — test whether items from the same portfolio are usually used together or are mutually exclusive. Use descriptive structural analysis.
7. **Adoption prediction with combined context** — predict whether a user will adopt an item using both relationship/shared-activity signals and the user's existing item profile. Use PyG node classification or link prediction with network context.

Cold-start recommendation, bundle/cross-sell analysis, and adoption prediction should work together. The combined predictive model should incorporate social relationships, shared activity, and user-item history rather than creating separate competing explanations for the same adoption outcome. The exact implementation may use a shared feature set, one heterogeneous graph model, or a staged pipeline.

---

## Layer 4: Review / Influence Graph

This layer models influence through contributions, helpfulness or validation signals, and followed trusted sources. Reviews and curators are examples; other companies can substitute posts, experts, creators, advisors, approvers, or internal champions.

1. **Trusted contributor identification** — surface users whose contributions are repeatedly validated, weighted by voter trust rather than raw counts. Use eigenvector- or PageRank-style centrality.
2. **Influential source identification** — surface trusted sources with large, engaged follower bases using degree/eigenvector centrality.
3. **Contribution credibility weighting** — rank reviews, posts, or recommendations by contributor centrality rather than raw helpfulness alone.
4. **Source recommendation to adoption influence** — predict whether a user adopts an item because a followed source recommended it. Use PyG link prediction or node classification.
5. **Contributor to adoption influence** — predict whether a user adopts an item because a trusted contributor evaluated it positively. Use PyG with network context.
6. **Coordinated manipulation detection** — identify clusters of accounts that validate one another in unusually dense, reciprocal patterns. Use NetworkX community detection, density, and reciprocity.
7. **Source authenticity/quality scoring** — measure whether recommendations correlate with follower adoption or satisfaction. Use descriptive overlap/correlation, with PyG only if extended to prediction.
8. **Influence-network bridge detection** — identify contributors or sources bridging otherwise separate user-profile clusters. Use betweenness centrality.

Source and contributor influence should feed the same combined adoption-prediction framework as Layer 3 so that each relationship type contributes an explainable signal instead of producing duplicate standalone purchase/adoption models.

---

## Schema Structure

The schema covers all four graph layers and all chosen use cases. Names should be configurable for each company's domain. The following is a table-level design; foreign keys, edge direction, and whether projections are computed or stored should be finalized during implementation.

### Core entity tables

- `users` — `user_id`, `join_date`, `organization_id`, and company-specific base attributes
- `items` — `item_id`, name/title, category tags, owner/provider, and release/creation date
- `trusted_sources` — `source_id`, name, source type, and follower count if stored
- `organizations` — `organization_id`, name, type, and hierarchy/tenant metadata

### Layer 1 — User relationship graph

- `relationship_edges` — `user_id_a`, `user_id_b`, `relationship_type`, `connection_date`, with edge direction defined by type
- `referrals` — `referred_user_id`, `referrer_user_id`, `referral_source`, `timestamp`

### Layer 2 — Shared activity graph

- `activity_sessions` — `session_id`, `item_id`, `activity_type`, `timestamp`, `duration`
- `activity_session_participants` — `session_id`, `user_id`
- Derived `shared_activity_edges` — `user_id_a`, `user_id_b`, `frequency`, `total_shared_duration`, and activity type

### Layer 3 — User–item bipartite graph

- `user_item_interactions` — `user_id`, `item_id`, `interaction_type`, `interaction_date`, `usage_total`, and optional transaction value
- Derived `item_item_projection` — `item_id_a`, `item_id_b`, `shared_user_count`

### Layer 4 — Review/influence graph

- `contributions` — `contribution_id`, `user_id`, `item_id`, content/rating, `timestamp`
- `contribution_validation_events` — `voter_user_id`, `contribution_id`, validation type, `timestamp`
- `source_follows` — `user_id`, `source_id`, `follow_date`
- `source_recommendations` — `source_id`, `item_id`, `recommendation_date`

### Supporting tables

- `community_participation` — `user_id`, `post_id`, `timestamp`, `engagement_received`
- `support_tickets` — `user_id`, `ticket_id`, `timestamp`, `severity`, status
- `feature_exposure_log` — `user_id`, `feature_id`, `exposed_flag`, `timestamp`, `experiment_id`, `variant`
- `churn_events` — `user_id`, `churn_date` or `last_active_date`
- `onboarding_events` — `user_id`, `onboarding_flow_type`, `completion_status`
- `trust_safety_events` — `user_id`, event type, severity, `timestamp`

### Ground-truth / simulation controls

- `planted_influence_rules` — records the propagation rules and parameters used by the synthetic generator. Keep this separate from model inputs so predictions can be evaluated against known ground truth without leaking the answer.

---

## Data Generation Scale

Use a scale large enough to create realistic network effects while keeping centrality analysis and GNN training tractable on normal development hardware.

### Core entities

- `users`: approximately **10,000**
- `items`: approximately **1,000**
- `trusted_sources`: approximately **300**
- `organizations`: enough to create meaningful within- and cross-organization relationships

### Relationship/event tables

- `relationship_edges`: average degree 8–20, producing roughly **80,000–200,000 edges** with power-law skew
- `activity_sessions`: roughly 20–50 sessions per active user, producing **200,000–500,000 sessions**, with 2–8 participant rows per session
- `user_item_interactions`: average 15–40 items per user, producing **150,000–400,000 rows**
- `contributions`: roughly 5–10% of eligible user-item interactions, producing **8,000–40,000 rows**
- `contribution_validation_events`: **20,000–60,000 rows**, skewed toward a minority of contributions
- `source_follows`: average 3–8 sources per user, producing **30,000–80,000 rows** with power-law source popularity
- `source_recommendations`: approximately **6,000–30,000 rows**, based on source activity

Distribution shape matters more than volume. Uniform random generation would produce technically valid but analytically weak data: centrality scores would converge, communities would look arbitrary, and PyG would have little realistic structure to learn.

---

## Data Generation Rules

### 1. Users — attributes and timing

- Spread `join_date` across a defined simulation window using a growth curve with a slow start, acceleration, and plateau.
- Assign each user a hidden lognormal-like activity propensity that drives relationship count, item interactions, contribution frequency, and other behavior. This creates realistic correlations across tables.
- Assign users to organizations, segments, or communities with both strong internal connectivity and a smaller number of cross-boundary bridges.

### 2. Relationship edges

- Use preferential attachment or a similar mechanism instead of pure random pairing to create hub/peripheral skew.
- Ensure `connection_date` is on or after both users' `join_date`.
- Support multiple typed edges while keeping their meanings separable.

### 3. Shared activity sessions

- Draw roughly 70–80% of sessions from existing relationship neighborhoods and the remainder from matched or random users. This keeps the activity graph related to, but distinct from, the explicit relationship graph.
- Correlate the session item or topic with participants' hidden preference clusters rather than sampling uniformly.

### 4. User–item interactions

- Give each item a hidden lognormal or power-law popularity score so a few items are widely adopted and many are niche.
- Weight interaction probability by both item popularity and the user's hidden preference or need cluster. This is necessary for meaningful item and user clustering.

### 5. Contributions and validation

- Scale contribution probability with user activity propensity.
- Give each contribution a hidden quality score. Validation events should be power-law distributed toward higher-quality contributions and more likely to come from users related to the contributor through social, activity, organization, or shared-item context.

### 6. Trusted-source follows and recommendations

- Distribute follower counts using a power-law or Zipf distribution.
- Give each source a specialization or preference cluster and align its recommendations with that specialization so authenticity scoring has a real signal.

### 7. Planted influence/propagation rules

Use five configurable influence families:

- adoption/conversion
- community participation
- usage/activity level
- trusted-source influence
- contributor influence

All families should share one rule engine and parameter format. Each rule defines a trigger event, probability or effect boost for connected nodes, decay window, eligible edge types, and optional organization/segment constraints.

Store rules and parameters in `planted_influence_rules`. Keep the effect size moderate and tunable: an effect that is too strong makes recovery trivial, while one that is too weak becomes indistinguishable from noise.

### 8. Time-based consistency

All event timestamps must respect causal order. Examples: no contribution before the related interaction, no shared activity before all participants have joined, no influence outcome before its trigger, and no relationship-based propagation before the relationship exists. Run a separate validation pass after generation rather than relying only on generator logic.

---

## Visual / Dashboard Design

### Network rendering

Do not render the full raw graph by default. A graph with around 10,000 users and 80,000–200,000 or more edges is beyond what a force-directed layout can show meaningfully. Use filtered and aggregated views.

### Entry points into node views

Give product managers four entry paths:

1. **Ranked list** — a sortable/filterable list of nodes ranked by betweenness and eigenvector centrality. Selecting a row opens the node's ego network.
2. **Alerts** — proactively surface flagged nodes or clusters, such as experiment contamination or support escalation risk, with the relevant filtered graph attached.
3. **Search/lookup** — search by user, item, organization, or source and open its local graph context.
4. **Cluster drill-down** — begin with aggregated community bubbles, drill into a cluster, inspect its most central nodes, and then open an individual ego network.

### Layer selection

- View Layers 1, 2, 3, or 4 individually.
- View all layers together.
- Create a custom view from any subset of layers and edge types.

### Non-graph-native output

Relationship, activity, and influence layers naturally support ego-network views. User-item recommendations and some predictive outputs are primarily score- or list-based. Show these in separate information blocks below or beside the graph rather than forcing every output into a node-link visualization. Combined prediction output should include a per-layer contribution breakdown.

### Use-case section

The eight chosen use cases form a separate top-level dashboard section. Where meaningful, allow switching between the most important and least important nodes.

Metric definitions:

1. **A/B contamination** — connection strength and influence strength
2. **Champion/super-connector churn risk** — eigenvector centrality plus engagement/activity signal, with weighting finalized during implementation
3. **Feature rollout sequencing** — eigenvector centrality
4. **User research prioritization** — community-validated influence rather than raw connectivity
5. **Support/moderation escalation** — betweenness centrality
6. **Onboarding flow decisioning** — binary existing-connection signal; exempt from most/least-important ranking
7. **Feature discovery gap detection** — isolation or distance from exposure; exempt from importance ranking
8. **Fraud/fake-account ring detection** — density and reciprocity pattern; exempt from importance ranking

### Explainability requirements

Every alert or prediction should expose:

- the relevant local network or cluster
- the metric or model output that triggered the result
- the edge types and behavioral signals that contributed
- a plain-language explanation
- a recommended product action
- uncertainty or confidence where applicable

---

## Why This Project Matters

Most product analysis treats users as independent rows. This project treats connection structure as part of the decision itself. It asks how relationships between users, organizations, activities, items, and sources change what a product team should do.

The system should help teams move from isolated questions such as "who may churn?" or "did the test win?" to network-aware questions such as:

- Which users or clusters could spread an outcome?
- Is an experiment invalid because its cohorts are connected?
- Which rollout cohort will create the right exposure and learning?
- Which seemingly weak segment simply never received the feature?
- Which user's problem has the largest likely blast radius?
- Which recommendation or contribution is trusted by the surrounding community?

Synthetic data allows the prototype to demonstrate these mechanisms without requiring access to any company's private production data. The result should be a reusable graph-intelligence framework whose entities, edge types, events, and rules can be configured for different companies and products.
