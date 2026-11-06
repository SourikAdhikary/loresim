"""Immutable domain types and stage choreography data structures for LoreSim."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LocationNode:
    location_id: str
    name: str
    region: str = "Core"
    parent_location_id: str | None = None
    x_coord: float = 0.0
    y_coord: float = 0.0
    description: str = ""


@dataclass(frozen=True)
class RouteEdge:
    route_id: str
    from_location_id: str
    to_location_id: str
    transport_mode: str = "walk"
    travel_minutes: int = 30
    bidirectional: bool = True


@dataclass(frozen=True)
class AgentProfile:
    agent_id: str
    name: str
    role: str = "Citizen"
    traits: tuple[str, ...] = ()
    attributes: dict[str, Any] = field(default_factory=dict)
    secret_agenda: str = ""
    created_tick: int = 0


@dataclass(frozen=True)
class ItemEntity:
    item_id: str
    name: str
    is_unique: bool = True
    description: str = ""
    icon: str = "🗡️"


@dataclass(frozen=True)
class CanonicalFact:
    fact_id: str
    branch_id: str
    created_tick: int
    subject: str
    predicate: str
    obj: str
    objective_truth: bool = True
    origin_event_id: str = ""
    importance: float = 1.0
    invalidated_tick: int | None = None


@dataclass(frozen=True)
class EpistemicBelief:
    belief_id: str
    branch_id: str
    tick: int
    agent_id: str
    fact_id: str
    stance: str  # BELIEVES_TRUE | BELIEVES_FALSE | SUSPECTS | WITHHOLDS_SECRET
    confidence: float
    modality: str  # FIRSTHAND | HEARSAY | EAVESDROP | INFERRED | DECEIVED
    source_agent_id: str
    acquired_event_id: str
    is_secret: bool = False
    subject: str = ""
    predicate: str = ""
    obj: str = ""
    objective_truth: bool = True


@dataclass(frozen=True)
class WorldEvent:
    event_id: str
    branch_id: str
    tick: int
    story_time_minutes: int
    chapter_ref: str
    event_type: str  # WITNESS_ACTION | MOVE | TELL | LIE | EAVESDROP | GIVE_ITEM | TAKE_ITEM | DEATH | ATTRIBUTE
    location_id: str
    actor_id: str
    target_ids: tuple[str, ...] = ()
    visibility: str = "PUBLIC_HERE"  # PUBLIC_HERE | WHISPER | STEALTH
    summary: str = ""
    raw_text: str = ""
    claims: tuple[dict[str, Any], ...] = ()
    item_id: str | None = None
    preconditions: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ContinuityViolation:
    violation_id: str
    branch_id: str
    tick: int
    rule_code: str  # LINT-01 .. LINT-07
    severity: str  # ERROR | WARNING
    actor_id: str
    event_id: str
    description: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NarrativeThread:
    thread_id: str
    branch_id: str
    title: str
    category: str
    introduced_tick: int
    last_touched_tick: int
    resolved_tick: int | None = None
    status: str = "OPEN"  # OPEN | RESOLVED | DORMANT
    payoff_notes: str = ""


@dataclass(frozen=True)
class BlastRadiusItem:
    broken_event_id: str
    tick: int
    actor_id: str
    summary: str
    broken_reason: str
    causal_chain: tuple[str, ...]


@dataclass(frozen=True)
class PuppetKeyframe:
    agent_id: str
    name: str
    role: str
    location_id: str
    x: float
    y: float
    expression: str  # NEUTRAL | SCHEMING | LYING_SWEAT | SHOCK | SUSPICIOUS | DEAD
    contagion_color: str  # BLUE_TRUTH | RED_LIE | GOLD_DECEIVER | GREY_UNAWARE
    held_items: tuple[str, ...] = ()
    public_speech: str = ""
    god_mode_thought: str = ""
    composure: float = 100.0
    voice_pitch: float = 1.0
    voice_rate: float = 1.0


@dataclass(frozen=True)
class EarshotRingKeyframe:
    speaker_id: str
    x: float
    y: float
    radius_px: float
    ring_type: str  # HONEST_CYAN | LIE_CRIMSON | EAVESDROP_GOLD
    label: str


@dataclass(frozen=True)
class ItemArcKeyframe:
    item_id: str
    item_name: str
    icon: str
    from_x: float
    from_y: float
    to_x: float
    to_y: float
    arc_points: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class StageFrame:
    branch_id: str
    tick: int
    story_time: str
    event_id: str
    headline: str
    dramatic_irony_score: float
    puppets: tuple[PuppetKeyframe, ...]
    earshot_rings: tuple[EarshotRingKeyframe, ...] = ()
    item_arcs: tuple[ItemArcKeyframe, ...] = ()


@dataclass(frozen=True)
class InvariantCheckResult:
    code: str
    name: str
    passed: bool
    detail: str
