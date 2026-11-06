"""Agent registry, vital status tracking, location occupancy, and trust/affection matrix."""

from __future__ import annotations

import json
import uuid
from typing import Any

from loresim.core.types import AgentProfile
from loresim.storage.db import SQLiteDatabase


class AgentRegistry:
    """Manages characters, their bi-temporal states, immutable attributes, and relationships."""

    def __init__(self, db: SQLiteDatabase) -> None:
        self.db = db

    def register_agent(
        self,
        agent_id: str,
        name: str,
        role: str = "Citizen",
        traits: tuple[str, ...] | list[str] = (),
        attributes: dict[str, Any] | None = None,
        secret_agenda: str = "",
        initial_location_id: str | None = None,
        branch_ref: str = "main",
        tick: int = 0,
    ) -> AgentProfile:
        attrs = dict(attributes or {})
        profile = AgentProfile(
            agent_id=agent_id,
            name=name,
            role=role,
            traits=tuple(traits),
            attributes=attrs,
            secret_agenda=secret_agenda,
            created_tick=int(tick),
        )
        with self.db.transaction():
            self.db.execute(
                """
                INSERT OR REPLACE INTO agents
                (agent_id, name, role, traits_json, attributes_json, secret_agenda, created_tick)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.agent_id,
                    profile.name,
                    profile.role,
                    json.dumps(list(profile.traits)),
                    json.dumps(profile.attributes, sort_keys=True),
                    profile.secret_agenda,
                    profile.created_tick,
                ),
            )
            if initial_location_id is not None:
                self.set_agent_state(
                    agent_id=agent_id,
                    location_id=initial_location_id,
                    vital_status="ALIVE",
                    mood="NEUTRAL",
                    tick=tick,
                    branch_ref=branch_ref,
                )
        return profile

    def get_agent(self, agent_id: str) -> AgentProfile | None:
        row = self.db.fetchone("SELECT * FROM agents WHERE agent_id = ?", (agent_id,))
        if row is None:
            return None
        return AgentProfile(
            agent_id=str(row["agent_id"]),
            name=str(row["name"]),
            role=str(row["role"]),
            traits=tuple(json.loads(str(row["traits_json"]))),
            attributes=json.loads(str(row["attributes_json"])),
            secret_agenda=str(row["secret_agenda"]),
            created_tick=int(row["created_tick"]),
        )

    def list_agents(self) -> list[AgentProfile]:
        rows = self.db.fetchall("SELECT * FROM agents ORDER BY agent_id")
        return [
            AgentProfile(
                agent_id=str(r["agent_id"]),
                name=str(r["name"]),
                role=str(r["role"]),
                traits=tuple(json.loads(str(r["traits_json"]))),
                attributes=json.loads(str(r["attributes_json"])),
                secret_agenda=str(r["secret_agenda"]),
                created_tick=int(r["created_tick"]),
            )
            for r in rows
        ]

    def set_agent_state(
        self,
        agent_id: str,
        location_id: str,
        vital_status: str = "ALIVE",
        mood: str = "NEUTRAL",
        tick: int = 0,
        branch_ref: str = "main",
    ) -> None:
        branch_id = self.db.resolve_branch_id(branch_ref)
        state_id = f"ast_{uuid.uuid4().hex[:12]}"
        self.db.execute(
            """
            INSERT INTO agent_states (state_id, branch_id, tick, agent_id, location_id, vital_status, mood)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (state_id, branch_id, int(tick), agent_id, location_id, vital_status, mood),
        )

    def get_agent_state(
        self, agent_id: str, branch_ref: str = "main", query_tick: int | None = None
    ) -> dict[str, Any]:
        """Resolve an agent's `(location_id, vital_status, mood, tick)` at `(branch_ref, query_tick)`."""
        bounds = self.db.get_branch_ancestry_bounds(branch_ref, query_tick)
        best: dict[str, Any] = {
            "agent_id": agent_id,
            "location_id": "unknown",
            "vital_status": "ALIVE",
            "mood": "NEUTRAL",
            "tick": 0,
        }
        for b_id, cap_tick in bounds:
            row = self.db.fetchone(
                """
                SELECT location_id, vital_status, mood, tick
                FROM agent_states
                WHERE branch_id = ? AND agent_id = ? AND tick <= ?
                ORDER BY tick DESC, rowid DESC
                LIMIT 1
                """,
                (b_id, agent_id, cap_tick),
            )
            if row is not None:
                best = {
                    "agent_id": agent_id,
                    "location_id": str(row["location_id"]),
                    "vital_status": str(row["vital_status"]),
                    "mood": str(row["mood"]),
                    "tick": int(row["tick"]),
                }
        return best

    def get_colocated_agents(
        self, location_id: str, branch_ref: str = "main", query_tick: int | None = None
    ) -> list[str]:
        """Return all `ALIVE` agents occupying `location_id` at `(branch_ref, query_tick)`."""
        colocated: list[str] = []
        for agent in self.list_agents():
            state = self.get_agent_state(agent.agent_id, branch_ref=branch_ref, query_tick=query_tick)
            if state["location_id"] == location_id and state["vital_status"] == "ALIVE":
                colocated.append(agent.agent_id)
        return colocated

    def set_relationship(
        self,
        from_agent_id: str,
        to_agent_id: str,
        trust: float,
        affection: float = 0.0,
        relation_label: str = "Acquaintance",
        tick: int = 0,
        branch_ref: str = "main",
    ) -> None:
        branch_id = self.db.resolve_branch_id(branch_ref)
        rel_id = f"rel_{uuid.uuid4().hex[:12]}"
        clamped_trust = max(-1.0, min(1.0, float(trust)))
        clamped_aff = max(-1.0, min(1.0, float(affection)))
        self.db.execute(
            """
            INSERT INTO relationships
            (rel_id, branch_id, tick, from_agent_id, to_agent_id, trust, affection, relation_label)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rel_id,
                branch_id,
                int(tick),
                from_agent_id,
                to_agent_id,
                clamped_trust,
                clamped_aff,
                relation_label,
            ),
        )

    def get_trust(
        self,
        from_agent_id: str,
        to_agent_id: str,
        branch_ref: str = "main",
        query_tick: int | None = None,
    ) -> float:
        if from_agent_id == to_agent_id:
            return 1.0
        bounds = self.db.get_branch_ancestry_bounds(branch_ref, query_tick)
        trust = 0.65  # Default baseline social trust
        for b_id, cap_tick in bounds:
            row = self.db.fetchone(
                """
                SELECT trust FROM relationships
                WHERE branch_id = ? AND from_agent_id = ? AND to_agent_id = ? AND tick <= ?
                ORDER BY tick DESC, rowid DESC
                LIMIT 1
                """,
                (b_id, from_agent_id, to_agent_id, cap_tick),
            )
            if row is not None:
                trust = float(row["trust"])
        return trust
