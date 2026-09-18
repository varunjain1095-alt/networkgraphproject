-- Schema version 1.0.0 — Network Graph Intelligence (SQLite)
PRAGMA foreign_keys = ON;

CREATE TABLE organizations (
    organization_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    org_type TEXT NOT NULL,
    parent_organization_id TEXT REFERENCES organizations(organization_id),
    created_at TEXT NOT NULL
);

CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(organization_id),
    display_name TEXT NOT NULL,
    join_date TEXT NOT NULL,
    last_active_date TEXT NOT NULL,
    activity_propensity REAL NOT NULL,
    taste_cluster_id INTEGER NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE items (
    item_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    provider TEXT,
    category_tags TEXT,
    release_date TEXT NOT NULL,
    popularity_score REAL NOT NULL,
    taste_cluster_id INTEGER NOT NULL
);

CREATE TABLE trusted_sources (
    source_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    specialization_cluster_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    follower_count_stored INTEGER
);

CREATE TABLE relationship_edges (
    edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id_a TEXT NOT NULL REFERENCES users(user_id),
    user_id_b TEXT NOT NULL REFERENCES users(user_id),
    relationship_type TEXT NOT NULL,
    connection_date TEXT NOT NULL,
    organization_scope TEXT,
    CHECK (user_id_a != user_id_b)
);

CREATE UNIQUE INDEX uq_rel_undirected
    ON relationship_edges(user_id_a, user_id_b, relationship_type);

CREATE TABLE referrals (
    referral_id INTEGER PRIMARY KEY AUTOINCREMENT,
    referred_user_id TEXT NOT NULL UNIQUE REFERENCES users(user_id),
    referrer_user_id TEXT NOT NULL REFERENCES users(user_id),
    referral_source TEXT NOT NULL,
    referral_timestamp TEXT NOT NULL
);

CREATE TABLE activity_sessions (
    session_id TEXT PRIMARY KEY,
    item_id TEXT REFERENCES items(item_id),
    activity_type TEXT NOT NULL,
    session_timestamp TEXT NOT NULL,
    duration_seconds INTEGER NOT NULL,
    organization_scope TEXT
);

CREATE TABLE activity_session_participants (
    session_id TEXT NOT NULL REFERENCES activity_sessions(session_id),
    user_id TEXT NOT NULL REFERENCES users(user_id),
    role TEXT,
    PRIMARY KEY (session_id, user_id)
);

CREATE TABLE user_item_interactions (
    interaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    item_id TEXT NOT NULL REFERENCES items(item_id),
    interaction_type TEXT NOT NULL,
    interaction_date TEXT NOT NULL,
    usage_total REAL NOT NULL DEFAULT 0,
    transaction_value REAL
);

CREATE TABLE contributions (
    contribution_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    item_id TEXT REFERENCES items(item_id),
    content TEXT,
    rating REAL,
    contribution_timestamp TEXT NOT NULL,
    quality_score REAL NOT NULL
);

CREATE TABLE contribution_validation_events (
    validation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    contribution_id TEXT NOT NULL REFERENCES contributions(contribution_id),
    voter_user_id TEXT NOT NULL REFERENCES users(user_id),
    validation_type TEXT NOT NULL,
    validation_timestamp TEXT NOT NULL,
    UNIQUE (contribution_id, voter_user_id, validation_type)
);

CREATE TABLE source_follows (
    user_id TEXT NOT NULL REFERENCES users(user_id),
    source_id TEXT NOT NULL REFERENCES trusted_sources(source_id),
    follow_date TEXT NOT NULL,
    PRIMARY KEY (user_id, source_id)
);

CREATE TABLE source_recommendations (
    recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL REFERENCES trusted_sources(source_id),
    item_id TEXT NOT NULL REFERENCES items(item_id),
    recommendation_date TEXT NOT NULL
);

CREATE TABLE community_participation (
    post_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    post_timestamp TEXT NOT NULL,
    engagement_received INTEGER NOT NULL DEFAULT 0,
    topic_tag TEXT
);

CREATE TABLE support_tickets (
    ticket_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    ticket_timestamp TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    category TEXT
);

CREATE TABLE feature_exposure_log (
    exposure_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    feature_id TEXT NOT NULL,
    experiment_id TEXT NOT NULL,
    variant TEXT NOT NULL,
    exposed_flag INTEGER NOT NULL,
    exposure_timestamp TEXT NOT NULL
);

CREATE TABLE churn_events (
    user_id TEXT PRIMARY KEY REFERENCES users(user_id),
    churn_date TEXT,
    last_active_date TEXT NOT NULL,
    churn_type TEXT NOT NULL
);

CREATE TABLE onboarding_events (
    onboarding_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    onboarding_flow_type TEXT NOT NULL,
    assigned_timestamp TEXT NOT NULL,
    completion_status TEXT NOT NULL,
    had_active_connection_at_start INTEGER NOT NULL
);

CREATE TABLE trust_safety_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    event_timestamp TEXT NOT NULL
);

CREATE TABLE planted_influence_rules (
    rule_id TEXT PRIMARY KEY,
    influence_family TEXT NOT NULL,
    trigger_event TEXT NOT NULL,
    eligible_edge_types TEXT NOT NULL,
    effect_boost REAL NOT NULL,
    base_probability REAL NOT NULL,
    decay_window_days INTEGER NOT NULL,
    max_hops INTEGER NOT NULL DEFAULT 1,
    org_constraint TEXT,
    seed INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE influence_outcomes (
    outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id TEXT NOT NULL REFERENCES planted_influence_rules(rule_id),
    source_user_id TEXT NOT NULL REFERENCES users(user_id),
    target_user_id TEXT NOT NULL REFERENCES users(user_id),
    edge_type_used TEXT NOT NULL,
    outcome_event_type TEXT NOT NULL,
    outcome_timestamp TEXT NOT NULL,
    reference_entity_id TEXT
);

CREATE TABLE dataset_metadata (
    dataset_id INTEGER PRIMARY KEY,
    generated_at TEXT NOT NULL,
    generator_seed INTEGER NOT NULL,
    config_hash TEXT NOT NULL,
    scale_mode TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    user_count INTEGER NOT NULL,
    edge_count_relationship INTEGER NOT NULL,
    session_count INTEGER NOT NULL
);

CREATE TABLE node_metrics (
    node_id TEXT NOT NULL,
    node_type TEXT NOT NULL,
    graph_layer TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    community_id INTEGER,
    computed_at TEXT NOT NULL,
    PRIMARY KEY (node_id, node_type, graph_layer, metric_name)
);

CREATE TABLE cluster_metrics (
    community_id INTEGER NOT NULL,
    graph_layer TEXT NOT NULL,
    node_count INTEGER NOT NULL,
    density REAL NOT NULL,
    reciprocity REAL,
    avg_exposure_rate REAL,
    computed_at TEXT NOT NULL,
    PRIMARY KEY (community_id, graph_layer)
);

CREATE TABLE pairwise_connection_strength (
    user_id_a TEXT NOT NULL,
    user_id_b TEXT NOT NULL,
    relationship_strength REAL NOT NULL,
    activity_strength REAL NOT NULL,
    combined_strength REAL NOT NULL,
    shared_experiment_ids TEXT,
    PRIMARY KEY (user_id_a, user_id_b)
);

-- Core indexes (additional indexes added in later phases if needed)
CREATE INDEX idx_users_org ON users(organization_id);
CREATE INDEX idx_users_join_date ON users(join_date);
CREATE INDEX idx_users_last_active ON users(last_active_date);
CREATE INDEX idx_rel_edges_a ON relationship_edges(user_id_a);
CREATE INDEX idx_rel_edges_b ON relationship_edges(user_id_b);
CREATE INDEX idx_sessions_timestamp ON activity_sessions(session_timestamp);
CREATE INDEX idx_interactions_user ON user_item_interactions(user_id);
CREATE INDEX idx_interactions_item ON user_item_interactions(item_id);
