"""14 STRICT SQLite tables and FTS5 lexical index for the LoreSim bi-temporal kernel."""

from __future__ import annotations

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS worlds (
    world_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    calendar_epoch TEXT NOT NULL,
    created_at REAL NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS branches (
    branch_id TEXT PRIMARY KEY,
    world_id TEXT NOT NULL,
    name TEXT NOT NULL UNIQUE,
    parent_branch_id TEXT,
    fork_tick INTEGER NOT NULL,
    head_tick INTEGER NOT NULL,
    created_at REAL NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS locations (
    location_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    region TEXT NOT NULL,
    parent_location_id TEXT,
    x_coord REAL NOT NULL,
    y_coord REAL NOT NULL,
    description TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS routes (
    route_id TEXT PRIMARY KEY,
    from_location_id TEXT NOT NULL,
    to_location_id TEXT NOT NULL,
    transport_mode TEXT NOT NULL,
    travel_minutes INTEGER NOT NULL,
    bidirectional INTEGER NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    traits_json TEXT NOT NULL,
    attributes_json TEXT NOT NULL,
    secret_agenda TEXT NOT NULL,
    created_tick INTEGER NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS agent_states (
    state_id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    agent_id TEXT NOT NULL,
    location_id TEXT NOT NULL,
    vital_status TEXT NOT NULL,
    mood TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS relationships (
    rel_id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    from_agent_id TEXT NOT NULL,
    to_agent_id TEXT NOT NULL,
    trust REAL NOT NULL,
    affection REAL NOT NULL,
    relation_label TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS items (
    item_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    is_unique INTEGER NOT NULL,
    description TEXT NOT NULL,
    properties_json TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS item_ledger (
    entry_id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    item_id TEXT NOT NULL,
    holder_type TEXT NOT NULL,
    holder_id TEXT NOT NULL,
    event_id TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS world_events (
    event_id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    story_time_minutes INTEGER NOT NULL,
    chapter_ref TEXT NOT NULL,
    event_type TEXT NOT NULL,
    location_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    target_ids_json TEXT NOT NULL,
    visibility TEXT NOT NULL,
    summary TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    claims_json TEXT NOT NULL,
    item_id TEXT,
    preconditions_json TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS canonical_facts (
    fact_id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL,
    created_tick INTEGER NOT NULL,
    invalidated_tick INTEGER,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object TEXT NOT NULL,
    objective_truth INTEGER NOT NULL,
    origin_event_id TEXT NOT NULL,
    importance REAL NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS epistemic_beliefs (
    belief_id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    agent_id TEXT NOT NULL,
    fact_id TEXT NOT NULL,
    stance TEXT NOT NULL,
    confidence REAL NOT NULL,
    modality TEXT NOT NULL,
    source_agent_id TEXT NOT NULL,
    acquired_event_id TEXT NOT NULL,
    is_secret INTEGER NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS narrative_threads (
    thread_id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    introduced_tick INTEGER NOT NULL,
    last_touched_tick INTEGER NOT NULL,
    resolved_tick INTEGER,
    status TEXT NOT NULL,
    payoff_notes TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS continuity_violations (
    violation_id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    rule_code TEXT NOT NULL,
    severity TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    description TEXT NOT NULL,
    evidence_json TEXT NOT NULL
) STRICT;

CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
    fact_id UNINDEXED,
    subject,
    predicate,
    object,
    summary
);

CREATE INDEX IF NOT EXISTS idx_agent_states_lookup ON agent_states(branch_id, agent_id, tick);
CREATE INDEX IF NOT EXISTS idx_events_lookup ON world_events(branch_id, tick);
CREATE INDEX IF NOT EXISTS idx_beliefs_lookup ON epistemic_beliefs(branch_id, agent_id, tick);
CREATE INDEX IF NOT EXISTS idx_item_ledger_lookup ON item_ledger(branch_id, item_id, tick);
CREATE INDEX IF NOT EXISTS idx_relationships_lookup ON relationships(branch_id, from_agent_id, to_agent_id, tick);
"""

STRICT_TABLE_NAMES = (
    "worlds",
    "branches",
    "locations",
    "routes",
    "agents",
    "agent_states",
    "relationships",
    "items",
    "item_ledger",
    "world_events",
    "canonical_facts",
    "epistemic_beliefs",
    "narrative_threads",
    "continuity_violations",
)
