"""7-Rule Deterministic Continuity & Plot-Hole Compiler (LINT-01 .. LINT-07)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from loresim.compiler.threads import ChekhovThreadTracker
from loresim.core.types import ContinuityViolation, WorldEvent
from loresim.epistemic.firewall import EpistemicPromptFirewall
from loresim.epistemic.vault import EpistemicVault
from loresim.storage.db import SQLiteDatabase
from loresim.world.agents import AgentRegistry
from loresim.world.inventory import InventoryTracker
from loresim.world.spatial import SpatialTopology


class ContinuityCompiler:
    """Verifies events and full narrative timelines against all 7 formal continuity rules."""

    def __init__(
        self,
        db: SQLiteDatabase,
        spatial: SpatialTopology,
        inventory: InventoryTracker,
        agents: AgentRegistry,
        vault: EpistemicVault,
        firewall: EpistemicPromptFirewall,
        threads: ChekhovThreadTracker,
    ) -> None:
        self.db = db
        self.spatial = spatial
        self.inventory = inventory
        self.agents = agents
        self.vault = vault
        self.firewall = firewall
        self.threads = threads

    def record_violation(
        self,
        branch_ref: str,
        tick: int,
        rule_code: str,
        severity: str,
        actor_id: str,
        event_id: str,
        description: str,
        evidence: dict[str, Any] | None = None,
    ) -> ContinuityViolation:
        branch_id = self.db.resolve_branch_id(branch_ref)
        vid = f"vio_{uuid.uuid4().hex[:12]}"
        ev = dict(evidence or {})
        violation = ContinuityViolation(
            violation_id=vid,
            branch_id=branch_id,
            tick=int(tick),
            rule_code=rule_code,
            severity=severity,
            actor_id=actor_id,
            event_id=event_id,
            description=description,
            evidence=ev,
        )
        self.db.execute(
            """
            INSERT INTO continuity_violations
            (violation_id, branch_id, tick, rule_code, severity, actor_id, event_id, description, evidence_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                violation.violation_id,
                violation.branch_id,
                violation.tick,
                violation.rule_code,
                violation.severity,
                violation.actor_id,
                violation.event_id,
                violation.description,
                json.dumps(violation.evidence, sort_keys=True),
            ),
        )
        return violation

    def verify_event_before_commit(
        self,
        event: WorldEvent,
        prev_location_id: str | None,
        prev_story_minutes: int | None,
    ) -> list[ContinuityViolation]:
        """Run pre-execution continuity checks (`LINT-01` .. `LINT-05`, `LINT-07`) on `event`."""
        violations: list[ContinuityViolation] = []
        prior_tick = max(0, event.tick - 1)

        # LINT-04: Dead or Incapacitated Actor Action
        actor_state = self.agents.get_agent_state(
            event.actor_id, branch_ref=event.branch_id, query_tick=prior_tick
        )
        if actor_state["vital_status"] == "DEAD" and event.event_type != "RESURRECT":
            violations.append(
                self.record_violation(
                    branch_ref=event.branch_id,
                    tick=event.tick,
                    rule_code="LINT-04",
                    severity="ERROR",
                    actor_id=event.actor_id,
                    event_id=event.event_id,
                    description=(
                        f"Dead-Actor Action: '{event.actor_id}' is DEAD (since tick {actor_state['tick']}) "
                        f"but performs '{event.event_type}' at tick {event.tick}."
                    ),
                    evidence={"vital_status": "DEAD", "death_tick": actor_state["tick"]},
                )
            )

        # LINT-02: Spatial Teleportation Bound
        if (
            prev_location_id
            and prev_location_id != "unknown"
            and prev_location_id != event.location_id
            and prev_story_minutes is not None
        ):
            min_mins = self.spatial.min_travel_minutes(prev_location_id, event.location_id)
            elapsed = event.story_time_minutes - prev_story_minutes
            if min_mins > 0 and elapsed < min_mins:
                violations.append(
                    self.record_violation(
                        branch_ref=event.branch_id,
                        tick=event.tick,
                        rule_code="LINT-02",
                        severity="ERROR",
                        actor_id=event.actor_id,
                        event_id=event.event_id,
                        description=(
                            f"Spatial Teleportation: '{event.actor_id}' moved from '{prev_location_id}' "
                            f"to '{event.location_id}' in {elapsed}m, but minimum travel time is {min_mins}m."
                        ),
                        evidence={
                            "from_location": prev_location_id,
                            "to_location": event.location_id,
                            "elapsed_minutes": elapsed,
                            "min_required_minutes": min_mins,
                        },
                    )
                )

        # LINT-03: Linear Unique Item Conservation
        if event.item_id and event.event_type in ("GIVE_ITEM", "USE_ITEM", "DROP_ITEM"):
            item = self.inventory.get_item(event.item_id)
            if item is not None and item.is_unique:
                holder = self.inventory.get_current_holder(
                    event.item_id, branch_ref=event.branch_id, query_tick=prior_tick
                )
                if holder is not None and (holder[0] != "AGENT" or holder[1] != event.actor_id):
                    violations.append(
                        self.record_violation(
                            branch_ref=event.branch_id,
                            tick=event.tick,
                            rule_code="LINT-03",
                            severity="ERROR",
                            actor_id=event.actor_id,
                            event_id=event.event_id,
                            description=(
                                f"Inventory Violation: '{event.actor_id}' attempted '{event.event_type}' on "
                                f"unique item '{event.item_id}', which is held by {holder[0]}:{holder[1]} (tick {holder[2]})."
                            ),
                            evidence={
                                "item_id": event.item_id,
                                "actual_holder": f"{holder[0]}:{holder[1]}",
                                "holder_since_tick": holder[2],
                            },
                        )
                    )

        # LINT-01: Epistemic Secret Leak (via required precondition facts or raw text audit)
        req_facts = event.preconditions.get("requires_facts", [])
        actor_beliefs = self.vault.get_agent_beliefs(
            event.actor_id, branch_ref=event.branch_id, query_tick=prior_tick
        )
        for req_fid in req_facts:
            if req_fid not in actor_beliefs or actor_beliefs[req_fid].confidence <= 0.0:
                fact_obj = self.vault.get_fact(req_fid)
                prop = (
                    f"{fact_obj.subject} {fact_obj.predicate} {fact_obj.obj}"
                    if fact_obj
                    else req_fid
                )
                violations.append(
                    self.record_violation(
                        branch_ref=event.branch_id,
                        tick=event.tick,
                        rule_code="LINT-01",
                        severity="ERROR",
                        actor_id=event.actor_id,
                        event_id=event.event_id,
                        description=(
                            f"Epistemic Secret Leak: '{event.actor_id}' references/acts on fact '{prop}' "
                            f"({req_fid}) at tick {event.tick} without having learned it."
                        ),
                        evidence={"missing_fact_id": req_fid, "proposition": prop},
                    )
                )

        if event.raw_text and event.event_type in ("TELL", "DIALOGUE", "ACTION"):
            leaks = self.firewall.audit_utterance_for_leaks(
                agent_id=event.actor_id,
                utterance=event.raw_text,
                branch_ref=event.branch_id,
                query_tick=prior_tick,
                raise_on_leak=False,
            )
            for lk in leaks:
                # Avoid duplicate LINT-01 if already caught by requires_facts
                if lk["leaked_fact_id"] not in req_facts:
                    violations.append(
                        self.record_violation(
                            branch_ref=event.branch_id,
                            tick=event.tick,
                            rule_code="LINT-01",
                            severity="ERROR",
                            actor_id=event.actor_id,
                            event_id=event.event_id,
                            description=(
                                f"Epistemic Utterance Leak: '{event.actor_id}' mentions '{lk['proposition']}' "
                                f"at tick {event.tick} without holding it in EpistemicVault."
                            ),
                            evidence=lk,
                        )
                    )

        # LINT-05: Immutable Attribute Contradiction
        attr_assertions = event.preconditions.get("assert_attributes", {})
        if attr_assertions:
            profile = self.agents.get_agent(event.actor_id)
            if profile is not None:
                for attr_key, asserted_val in attr_assertions.items():
                    if attr_key in profile.attributes and profile.attributes[attr_key] != asserted_val:
                        violations.append(
                            self.record_violation(
                                branch_ref=event.branch_id,
                                tick=event.tick,
                                rule_code="LINT-05",
                                severity="ERROR",
                                actor_id=event.actor_id,
                                event_id=event.event_id,
                                description=(
                                    f"Immutable Attribute Contradiction: '{event.actor_id}.{attr_key}' "
                                    f"asserted as '{asserted_val}' at tick {event.tick}, contradicting "
                                    f"canonical value '{profile.attributes[attr_key]}'."
                                ),
                                evidence={
                                    "attribute": attr_key,
                                    "canonical_value": profile.attributes[attr_key],
                                    "asserted_value": asserted_val,
                                },
                            )
                        )

        # LINT-07: Epistemic Contradiction / Lie Exposure to Firsthand Witness
        if event.event_type in ("TELL", "LIE") and event.claims:
            for claim in event.claims:
                subj = str(claim.get("subject", ""))
                pred = str(claim.get("predicate", ""))
                obj = str(claim.get("object", ""))
                for target_id in event.target_ids:
                    contra = self.vault.find_contradicting_firsthand_belief(
                        agent_id=target_id,
                        subject=subj,
                        predicate=pred,
                        claimed_obj=obj,
                        branch_ref=event.branch_id,
                        query_tick=prior_tick,
                    )
                    if contra is not None:
                        violations.append(
                            self.record_violation(
                                branch_ref=event.branch_id,
                                tick=event.tick,
                                rule_code="LINT-07",
                                severity="WARNING",
                                actor_id=event.actor_id,
                                event_id=event.event_id,
                                description=(
                                    f"Lie Exposure: '{event.actor_id}' claims '{subj} {pred} {obj}' to "
                                    f"'{target_id}', who holds FIRSTHAND contradictory belief '{contra.subject} "
                                    f"{contra.predicate} {contra.obj}'."
                                ),
                                evidence={
                                    "speaker_id": event.actor_id,
                                    "listener_id": target_id,
                                    "contradicting_fact_id": contra.fact_id,
                                },
                            )
                        )

        return violations

    def audit_dangling_threads(
        self,
        branch_ref: str = "main",
        current_tick: int | None = None,
        threshold_ticks: int | None = None,
    ) -> list[ContinuityViolation]:
        """Run `LINT-06` (Dangling Chekhov Thread detector) and record violations."""
        branch_id = self.db.resolve_branch_id(branch_ref)
        head = current_tick if current_tick is not None else self.db.get_branch_head_tick(branch_id)
        self.db.advance_branch_head_tick(branch_id, head)
        dangling = self.threads.find_dangling_threads(
            branch_ref=branch_id, current_tick=head, threshold_ticks=threshold_ticks
        )
        recorded: list[ContinuityViolation] = []
        for thr in dangling:
            age = head - thr.last_touched_tick
            recorded.append(
                self.record_violation(
                    branch_ref=branch_ref,
                    tick=head,
                    rule_code="LINT-06",
                    severity="WARNING",
                    actor_id="narrator",
                    event_id=thr.thread_id,
                    description=(
                        f"Dangling Chekhov Thread: '{thr.title}' ({thr.category}) introduced at tick "
                        f"{thr.introduced_tick} has been untouched for {age} ticks."
                    ),
                    evidence={
                        "thread_id": thr.thread_id,
                        "title": thr.title,
                        "introduced_tick": thr.introduced_tick,
                        "dormant_ticks": age,
                    },
                )
            )
        return recorded

    def list_violations(
        self, branch_ref: str = "main", query_tick: int | None = None
    ) -> list[ContinuityViolation]:
        where_sql, params = self.db.build_bitemporal_sql_Clause(branch_ref, query_tick)
        rows = self.db.fetchall(
            f"SELECT * FROM continuity_violations WHERE {where_sql} ORDER BY tick ASC, rowid ASC",
            params,
        )
        return [
            ContinuityViolation(
                violation_id=str(r["violation_id"]),
                branch_id=str(r["branch_id"]),
                tick=int(r["tick"]),
                rule_code=str(r["rule_code"]),
                severity=str(r["severity"]),
                actor_id=str(r["actor_id"]),
                event_id=str(r["event_id"]),
                description=str(r["description"]),
                evidence=json.loads(str(r["evidence_json"])),
            )
            for r in rows
        ]
