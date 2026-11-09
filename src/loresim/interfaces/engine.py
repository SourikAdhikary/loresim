"""Unified high-level LoreSimEngine facade combining all 6 architectural layers."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from loresim.compiler.butterfly import ButterflyAnalyzer
from loresim.compiler.ingester import ManuscriptIngester
from loresim.compiler.linter import ContinuityCompiler
from loresim.compiler.threads import ChekhovThreadTracker
from loresim.core.config import LoreSimConfig
from loresim.core.errors import (
    AttributeContradictionError,
    DeadActorViolationError,
    EpistemicLeakTrap,
    InventoryViolationError,
    TeleportationViolationError,
)
from loresim.core.llm import LLMProvider
from loresim.core.types import ContinuityViolation, StageFrame, WorldEvent
from loresim.epistemic.firewall import EpistemicPromptFirewall
from loresim.epistemic.irony import DramaticIronyAnalyzer
from loresim.epistemic.propagator import EpistemicPropagator
from loresim.epistemic.vault import EpistemicVault
from loresim.simulator.doctor import LoreSimDoctor
from loresim.simulator.scene import SceneSimulator
from loresim.simulator.stage_director import StageDirector
from loresim.storage.db import SQLiteDatabase
from loresim.world.agents import AgentRegistry
from loresim.world.inventory import InventoryTracker
from loresim.world.spatial import SpatialTopology


class LoreSimEngine:
    """High-level facade for the LoreSim Epistemic World & Continuity Engine."""

    def __init__(
        self,
        workspace_root: Path | str,
        world_name: str = "DefaultWorld",
        strict_mode: bool = False,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self.config = LoreSimConfig(
            workspace_root=Path(workspace_root),
            world_name=world_name,
            strict_mode=strict_mode,
        )
        self.db = SQLiteDatabase(self.config)
        self.spatial = SpatialTopology(self.db)
        self.inventory = InventoryTracker(self.db)
        self.agents = AgentRegistry(self.db)
        self.vault = EpistemicVault(self.db)
        self.propagator = EpistemicPropagator(self.db, self.vault, self.agents)
        self.firewall = EpistemicPromptFirewall(self.vault, self.agents, self.inventory)
        self.irony = DramaticIronyAnalyzer(self.vault, self.agents)
        self.threads = ChekhovThreadTracker(
            self.db, stale_threshold_ticks=self.config.stale_thread_tick_threshold
        )
        self.linter = ContinuityCompiler(
            self.db,
            self.spatial,
            self.inventory,
            self.agents,
            self.vault,
            self.firewall,
            self.threads,
        )
        self.butterfly = ButterflyAnalyzer(self.db)
        self.ingester = ManuscriptIngester(
            spatial=self.spatial,
            agents=self.agents,
            inventory=self.inventory,
            llm_provider=llm_provider,
        )
        self.stage_director = StageDirector(
            self.db,
            self.spatial,
            self.inventory,
            self.agents,
            self.vault,
            self.irony,
        )
        self.simulator = SceneSimulator(
            self.db,
            self.agents,
            self.vault,
            self.firewall,
            self.irony,
            composure_crack_threshold=self.config.composure_crack_threshold,
            llm_provider=llm_provider,
        )
        self.doctor = LoreSimDoctor(
            self.db,
            self.spatial,
            self.inventory,
            self.agents,
            self.vault,
            self.firewall,
            self.simulator,
            self.butterfly,
        )

    def record_event(
        self,
        tick: int,
        location_id: str,
        actor_id: str,
        event_type: str,
        target_ids: list[str] | tuple[str, ...] = (),
        story_time_minutes: int | None = None,
        chapter_ref: str = "Ch1",
        visibility: str = "PUBLIC_HERE",
        summary: str = "",
        raw_text: str = "",
        claims: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
        item_id: str | None = None,
        preconditions: dict[str, Any] | None = None,
        is_secret: bool = False,
        branch_ref: str = "main",
        event_id: str | None = None,
        strict_override: bool | None = None,
    ) -> tuple[WorldEvent, list[ContinuityViolation]]:
        """Record an event at `(branch_ref, tick)`, run pre-commit continuity linting,
        and apply world state & epistemic belief transitions.
        """
        branch_id = self.db.resolve_branch_id(branch_ref)
        eid = event_id or f"ev_{uuid.uuid4().hex[:10]}"
        story_mins = int(tick * 30) if story_time_minutes is None else int(story_time_minutes)

        # Look up actor's previous location and previous event timestamp for LINT-02 travel checks
        prior_state = self.agents.get_agent_state(
            actor_id, branch_ref=branch_id, query_tick=max(0, tick - 1)
        )
        prev_loc = str(prior_state["location_id"])
        where_sql, params = self.db.build_bitemporal_sql_Clause(branch_id, max(0, tick - 1))
        prev_ev_row = self.db.fetchone(
            f"SELECT story_time_minutes FROM world_events WHERE {where_sql} AND actor_id = ? ORDER BY tick DESC, rowid DESC LIMIT 1",
            (*params, actor_id),
        )
        prev_mins = int(prev_ev_row["story_time_minutes"]) if prev_ev_row else 0

        ev = WorldEvent(
            event_id=eid,
            branch_id=branch_id,
            tick=int(tick),
            story_time_minutes=story_mins,
            chapter_ref=chapter_ref,
            event_type=event_type,
            location_id=location_id,
            actor_id=actor_id,
            target_ids=tuple(target_ids),
            visibility=visibility,
            summary=summary or f"{actor_id} {event_type} at {location_id}",
            raw_text=raw_text,
            claims=tuple(claims),
            item_id=item_id,
            preconditions=dict(preconditions or {}),
        )

        with self.db.transaction():
            violations = self.linter.verify_event_before_commit(ev, prev_loc, prev_mins)
            enforce_strict = self.config.strict_mode if strict_override is None else strict_override
            if enforce_strict and violations:
                first = violations[0]
                if first.rule_code == "LINT-01":
                    raise EpistemicLeakTrap(first.description)
                if first.rule_code == "LINT-02":
                    raise TeleportationViolationError(first.description)
                if first.rule_code == "LINT-03":
                    raise InventoryViolationError(first.description)
                if first.rule_code == "LINT-04":
                    raise DeadActorViolationError(first.description)
                if first.rule_code == "LINT-05":
                    raise AttributeContradictionError(first.description)

            # Persist event row
            self.db.execute(
                """
                INSERT INTO world_events
                (event_id, branch_id, tick, story_time_minutes, chapter_ref, event_type,
                 location_id, actor_id, target_ids_json, visibility, summary, raw_text,
                 claims_json, item_id, preconditions_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ev.event_id,
                    ev.branch_id,
                    ev.tick,
                    ev.story_time_minutes,
                    ev.chapter_ref,
                    ev.event_type,
                    ev.location_id,
                    ev.actor_id,
                    json.dumps(list(ev.target_ids)),
                    ev.visibility,
                    ev.summary,
                    ev.raw_text,
                    json.dumps(list(ev.claims)),
                    ev.item_id,
                    json.dumps(ev.preconditions, sort_keys=True),
                ),
            )
            self.db.advance_branch_head_tick(branch_id, ev.tick)

            # Apply physical state mutations
            cur_vital = str(prior_state["vital_status"])
            if ev.event_type == "DEATH":
                victim_id = ev.target_ids[0] if ev.target_ids else ev.actor_id
                self.agents.set_agent_state(
                    agent_id=victim_id,
                    location_id=ev.location_id,
                    vital_status="DEAD",
                    mood="DEAD",
                    tick=ev.tick,
                    branch_ref=branch_id,
                )
            elif cur_vital == "ALIVE":
                self.agents.set_agent_state(
                    agent_id=ev.actor_id,
                    location_id=ev.location_id,
                    vital_status="ALIVE",
                    mood="SCHEMING" if is_secret or ev.event_type == "LIE" else "ACTIVE",
                    tick=ev.tick,
                    branch_ref=branch_id,
                )

            # Apply item ledger mutations
            if ev.item_id:
                if ev.event_type == "TAKE_ITEM":
                    self.inventory.record_transfer(
                        item_id=ev.item_id,
                        to_holder_id=ev.actor_id,
                        to_holder_type="AGENT",
                        tick=ev.tick,
                        event_id=ev.event_id,
                        branch_ref=branch_id,
                    )
                elif ev.event_type == "GIVE_ITEM" and ev.target_ids:
                    self.inventory.record_transfer(
                        item_id=ev.item_id,
                        to_holder_id=ev.target_ids[0],
                        to_holder_type="AGENT",
                        tick=ev.tick,
                        event_id=ev.event_id,
                        branch_ref=branch_id,
                    )
                elif ev.event_type == "DROP_ITEM":
                    self.inventory.record_transfer(
                        item_id=ev.item_id,
                        to_holder_id=ev.location_id,
                        to_holder_type="LOCATION",
                        tick=ev.tick,
                        event_id=ev.event_id,
                        branch_ref=branch_id,
                    )

            # Apply epistemic belief propagation
            for cl in ev.claims:
                subj = str(cl.get("subject", ev.actor_id))
                pred = str(cl.get("predicate", ev.event_type.lower()))
                obj = str(cl.get("object", ""))
                secret_flag = bool(cl.get("is_secret", is_secret))
                if ev.event_type == "LIE":
                    listeners = list(ev.target_ids)
                    self.propagator.propagate_testimony(
                        speaker_id=ev.actor_id,
                        listener_ids=listeners,
                        subject=subj,
                        predicate=pred,
                        obj=obj,
                        tick=ev.tick,
                        event_id=ev.event_id,
                        is_lie=True,
                        modality="HEARSAY",
                        branch_ref=branch_id,
                    )
                elif ev.event_type in ("TELL", "EAVESDROP"):
                    listeners = list(ev.target_ids)
                    if ev.visibility == "PUBLIC_HERE":
                        coloc = self.agents.get_colocated_agents(
                            ev.location_id, branch_ref=branch_id, query_tick=ev.tick
                        )
                        listeners = list(set(listeners + coloc))
                    self.propagator.propagate_testimony(
                        speaker_id=ev.actor_id,
                        listener_ids=listeners,
                        subject=subj,
                        predicate=pred,
                        obj=obj,
                        tick=ev.tick,
                        event_id=ev.event_id,
                        is_lie=False,
                        modality="EAVESDROP" if ev.event_type == "EAVESDROP" else "HEARSAY",
                        branch_ref=branch_id,
                    )
                else:
                    if ev.visibility == "STEALTH" or secret_flag:
                        witnesses = [ev.actor_id, *ev.target_ids]
                    else:
                        coloc = self.agents.get_colocated_agents(
                            ev.location_id, branch_ref=branch_id, query_tick=ev.tick
                        )
                        witnesses = list(set([ev.actor_id, *ev.target_ids, *coloc]))
                    self.propagator.propagate_witness(
                        witness_ids=witnesses,
                        subject=subj,
                        predicate=pred,
                        obj=obj,
                        tick=ev.tick,
                        event_id=ev.event_id,
                        is_secret=secret_flag,
                        branch_ref=branch_id,
                    )

        return ev, violations

    def get_stage_frame(
        self, branch_ref: str = "main", tick: int | None = None, focus_fact_id: str | None = None
    ) -> StageFrame:
        return self.stage_director.compile_stage_frame(
            branch_ref=branch_ref, tick=tick, focus_fact_id=focus_fact_id
        )

    def ingest_manuscript(
        self,
        script_text: str,
        *,
        branch_ref: str = "main",
        use_llm: bool = False,
        strict_override: bool | None = None,
    ) -> dict[str, Any]:
        """Parse and record events from `@tick` DSL, Fountain screenplay, or natural-language prose."""
        parsed_events = self.ingester.parse_script_lines(script_text, use_llm=use_llm)
        recorded: list[WorldEvent] = []
        all_violations: list[ContinuityViolation] = []
        for ev_dict in parsed_events:
            ev, vios = self.record_event(
                tick=int(ev_dict["tick"]),
                story_time_minutes=int(ev_dict.get("story_time_minutes", int(ev_dict["tick"]) * 30)),
                chapter_ref=str(ev_dict.get("chapter_ref", "Ch1")),
                location_id=str(ev_dict["location_id"]),
                actor_id=str(ev_dict["actor_id"]),
                event_type=str(ev_dict["event_type"]),
                target_ids=list(ev_dict.get("target_ids", [])),
                visibility=str(ev_dict.get("visibility", "PUBLIC_HERE")),
                item_id=ev_dict.get("item_id"),
                claims=list(ev_dict.get("claims", [])),
                summary=str(ev_dict.get("summary", "")),
                raw_text=str(ev_dict.get("raw_text", "")),
                is_secret=any(bool(c.get("is_secret")) for c in ev_dict.get("claims", [])),
                branch_ref=branch_ref,
                strict_override=strict_override,
            )
            recorded.append(ev)
            all_violations.extend(vios)
        return {
            "events_count": len(recorded),
            "events": [asdict(e) for e in recorded],
            "violations_count": len(all_violations),
            "violations": [asdict(v) for v in all_violations],
        }

    def seed_demo_mystery_world(self) -> dict[str, Any]:
        """Seed a rich 4-room, 5-character Royal Treaty Conspiracy world for the 60 FPS Studio."""
        if self.agents.list_agents():
            return {"status": "already_seeded", "head_tick": self.db.get_branch_head_tick("main")}

        # 1. Locations (2D stage rooms)
        self.spatial.add_location("study", "Royal Study", "Citadel", x_coord=190.0, y_coord=160.0)
        self.spatial.add_location("great_hall", "Great Banquet Hall", "Citadel", x_coord=540.0, y_coord=160.0)
        self.spatial.add_location("courtyard", "Citadel Courtyard", "Citadel", x_coord=190.0, y_coord=410.0)
        self.spatial.add_location("tavern", "Harbor Tavern", "Docks", x_coord=540.0, y_coord=410.0)

        self.spatial.add_route("study", "great_hall", travel_minutes=5)
        self.spatial.add_route("great_hall", "courtyard", travel_minutes=10)
        self.spatial.add_route("courtyard", "tavern", travel_minutes=45)
        self.spatial.add_route("study", "courtyard", travel_minutes=10)

        # 2. Characters (NPCs)
        self.agents.register_agent(
            "vance",
            "Lord Vance",
            role="Chancellor",
            traits=("ambitious", "cunning"),
            attributes={"eye_color": "amber", "house": "Valen"},
            secret_agenda="Destroy the peace treaty and blame the Northern Rebels",
            initial_location_id="study",
            tick=0,
        )
        self.agents.register_agent(
            "clara",
            "Lady Clara",
            role="Ambassador",
            traits=("diplomatic", "trusting"),
            attributes={"eye_color": "blue", "house": "Aurelia"},
            secret_agenda="Sign the peace treaty before midnight",
            initial_location_id="great_hall",
            tick=0,
        )
        self.agents.register_agent(
            "kael",
            "Captain Kael",
            role="Royal Guard",
            traits=("observant", "loyal"),
            attributes={"eye_color": "green", "house": "Watch"},
            secret_agenda="Protect the Citadel and uncover traitors",
            initial_location_id="study",
            tick=0,
        )
        self.agents.register_agent(
            "mira",
            "Spymaster Mira",
            role="Whisper Broker",
            traits=("stealthy", "skeptical"),
            attributes={"eye_color": "grey", "house": "Shadow"},
            secret_agenda="Collect leverage on the high council",
            initial_location_id="great_hall",
            tick=0,
        )
        self.agents.register_agent(
            "thorne",
            "General Thorne",
            role="Warlord",
            traits=("aggressive", "impatient"),
            attributes={"eye_color": "brown", "house": "Iron"},
            secret_agenda="Mobilize the garrison if the treaty fails",
            initial_location_id="courtyard",
            tick=0,
        )

        # Initial trust relationships
        self.agents.set_relationship("clara", "vance", trust=0.82, relation_label="Allied Advisor", tick=0)
        self.agents.set_relationship("thorne", "clara", trust=0.75, relation_label="Commander", tick=0)
        self.agents.set_relationship("kael", "vance", trust=0.60, relation_label="Subordinate", tick=0)

        # 3. Unique Items
        self.inventory.register_item(
            "royal_treaty",
            "Royal Peace Treaty",
            is_unique=True,
            icon="📜",
            initial_holder_id="vance",
            tick=0,
        )
        self.inventory.register_item(
            "signet_dagger",
            "Valen Signet Dagger",
            is_unique=True,
            icon="🗡️",
            initial_holder_id="vance",
            tick=0,
        )
        self.inventory.register_item(
            "cipher_key",
            "Vault Cipher Key",
            is_unique=True,
            icon="🗝️",
            initial_holder_id="mira",
            tick=0,
        )

        # 4. Narrative Thread (Chekhov's Gun)
        self.threads.introduce_thread(
            title="The Missing Vault Cipher Key",
            category="Chekhov Artifact",
            introduced_tick=1,
            payoff_notes="Needed to open the Royal Archive in Act 3",
            thread_id="thr_cipher_key",
        )

        # 5. Story Events across Ticks 1..6
        # Tick 1: Vance secretly burns the Royal Treaty in the Study while Kael witnesses from the alcove!
        self.record_event(
            event_id="ev_01_burn_treaty",
            tick=1,
            story_time_minutes=60,
            location_id="study",
            actor_id="vance",
            target_ids=("kael",),
            event_type="WITNESS_ACTION",
            visibility="STEALTH",
            is_secret=True,
            summary="Lord Vance secretly burns the Royal Peace Treaty in the study hearth.",
            raw_text="Vance casts the Royal Peace Treaty into the study flames, unaware Kael saw the seal.",
            claims=({"subject": "vance", "predicate": "burned", "object": "royal_treaty", "is_secret": True},),
        )

        # Tick 2: Vance walks to the Great Hall and gives the Signet Dagger to Mira to hide
        self.record_event(
            event_id="ev_02_move_hall",
            tick=2,
            story_time_minutes=70,
            location_id="great_hall",
            actor_id="vance",
            target_ids=("mira",),
            event_type="GIVE_ITEM",
            visibility="WHISPER",
            item_id="signet_dagger",
            summary="Vance enters the Great Hall and slips the Valen Signet Dagger to Mira.",
            raw_text="Keep this Valen Signet Dagger out of sight until dawn.",
            claims=({"subject": "mira", "predicate": "holds", "object": "signet_dagger", "is_secret": True},),
        )

        # Tick 3: Vance tells a fabricated LIE to Lady Clara in the Great Hall
        self.record_event(
            event_id="ev_03_lie_clara",
            tick=3,
            story_time_minutes=80,
            location_id="great_hall",
            actor_id="vance",
            target_ids=("clara",),
            event_type="LIE",
            visibility="WHISPER",
            summary="Vance lies to Lady Clara that Northern Rebels stole the Royal Treaty.",
            raw_text="Tragic news, Clara! Northern Rebels broke into the study and stole the Royal Peace Treaty!",
            claims=({"subject": "northern_rebels", "predicate": "stole", "object": "royal_treaty"},),
            preconditions={"requires_events": ["ev_01_burn_treaty"]},
        )

        # Tick 4: Lady Clara (believing the lie!) walks to Courtyard and repeats the rumor to General Thorne
        self.record_event(
            event_id="ev_04_rumor_thorne",
            tick=4,
            story_time_minutes=95,
            location_id="courtyard",
            actor_id="clara",
            target_ids=("thorne",),
            event_type="TELL",
            visibility="PUBLIC_HERE",
            summary="Clara tells General Thorne the rumor that Northern Rebels stole the treaty.",
            raw_text="General Thorne, Northern Rebels stole the Royal Peace Treaty! Prepare the watch!",
            claims=({"subject": "northern_rebels", "predicate": "stole", "object": "royal_treaty"},),
            preconditions={"requires_events": ["ev_03_lie_clara"]},
        )

        # Tick 5: Kael moves to Great Hall and Vance tries the same lie on Kael -> LIE EXPOSURE!
        self.record_event(
            event_id="ev_05_lie_exposed",
            tick=5,
            story_time_minutes=105,
            location_id="great_hall",
            actor_id="vance",
            target_ids=("kael",),
            event_type="LIE",
            visibility="WHISPER",
            summary="Vance repeats the Rebel theft lie to Captain Kael—who witnessed Vance burn it!",
            raw_text="Captain Kael, Northern Rebels stole the Royal Peace Treaty from my desk!",
            claims=({"subject": "northern_rebels", "predicate": "stole", "object": "royal_treaty"},),
            preconditions={"requires_events": ["ev_01_burn_treaty"]},
        )

        return {
            "status": "seeded",
            "head_tick": self.db.get_branch_head_tick("main"),
            "frame": asdict(self.get_stage_frame("main")),
        }

    def close(self) -> None:
        self.db.close()
