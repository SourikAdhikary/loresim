"""Zero-Cost 60 FPS 2D NPC Stage Blocking & Puppet Choreography Compiler (`StageDirector`)."""

from __future__ import annotations

import hashlib
import json

from loresim.core.clock import format_minutes_to_story_time
from loresim.core.rust_bridge import rust_parabolic_item_arc
from loresim.core.types import (
    EarshotRingKeyframe,
    ItemArcKeyframe,
    PuppetKeyframe,
    StageFrame,
)
from loresim.epistemic.irony import DramaticIronyAnalyzer
from loresim.epistemic.vault import EpistemicVault
from loresim.storage.db import SQLiteDatabase
from loresim.world.agents import AgentRegistry
from loresim.world.inventory import InventoryTracker
from loresim.world.spatial import SpatialTopology


class StageDirector:
    """Compiles world events and epistemic state at `(branch, tick)` into a 60 FPS `StageFrame`."""

    def __init__(
        self,
        db: SQLiteDatabase,
        spatial: SpatialTopology,
        inventory: InventoryTracker,
        agents: AgentRegistry,
        vault: EpistemicVault,
        irony: DramaticIronyAnalyzer,
    ) -> None:
        self.db = db
        self.spatial = spatial
        self.inventory = inventory
        self.agents = agents
        self.vault = vault
        self.irony = irony

    @staticmethod
    def _voice_profile(agent_id: str) -> tuple[float, float]:
        """Deterministic Web Speech API `(pitch, rate)` per character (`$0.00` TTS cost)."""
        digest = int(hashlib.sha256(agent_id.encode("utf-8")).hexdigest()[:8], 16)
        pitch = round(0.78 + (digest % 55) / 100.0, 2)
        rate = round(0.92 + ((digest >> 8) % 24) / 100.0, 2)
        return pitch, rate

    def compile_stage_frame(
        self,
        branch_ref: str = "main",
        tick: int | None = None,
        focus_fact_id: str | None = None,
    ) -> StageFrame:
        head_tick = tick if tick is not None else self.db.get_branch_head_tick(branch_ref)
        where_sql, params = self.db.build_bitemporal_sql_Clause(branch_ref, head_tick)
        ev_row = self.db.fetchone(
            f"SELECT * FROM world_events WHERE {where_sql} ORDER BY tick DESC, rowid DESC LIMIT 1",
            params,
        )

        locations = {loc.location_id: loc for loc in self.spatial.list_locations()}
        all_agents = self.agents.list_agents()

        active_event_id = str(ev_row["event_id"]) if ev_row else "ev_init"
        active_actor = str(ev_row["actor_id"]) if ev_row else ""
        active_targets = json.loads(str(ev_row["target_ids_json"])) if ev_row else []
        active_type = str(ev_row["event_type"]) if ev_row else "IDLE"
        active_vis = str(ev_row["visibility"]) if ev_row else "PUBLIC_HERE"
        active_summary = str(ev_row["summary"]) if ev_row else "World Initialized"
        active_raw = str(ev_row["raw_text"]) if ev_row else ""
        active_item_id = ev_row["item_id"] if ev_row else None
        story_mins = int(ev_row["story_time_minutes"]) if ev_row else head_tick * 30

        puppets: list[PuppetKeyframe] = []
        agent_coords: dict[str, tuple[float, float]] = {}

        # Group agents by location so co-located puppets stand in a clean conversational semicircle
        loc_buckets: dict[str, list[str]] = {}
        agent_states: dict[str, dict[str, object]] = {}
        for ag in all_agents:
            st = self.agents.get_agent_state(ag.agent_id, branch_ref=branch_ref, query_tick=head_tick)
            agent_states[ag.agent_id] = st
            lid = str(st["location_id"])
            loc_buckets.setdefault(lid, []).append(ag.agent_id)

        for ag in all_agents:
            st = agent_states[ag.agent_id]
            lid = str(st["location_id"])
            loc_node = locations.get(lid)
            base_x = loc_node.x_coord if loc_node else 180.0
            base_y = loc_node.y_coord if loc_node else 180.0

            bucket = loc_buckets.get(lid, [ag.agent_id])
            slot = bucket.index(ag.agent_id)
            count = max(1, len(bucket))
            offset_x = (slot - (count - 1) / 2.0) * 52.0
            offset_y = (slot % 2) * 18.0 - 9.0
            px = round(base_x + offset_x, 1)
            py = round(base_y + offset_y, 1)
            agent_coords[ag.agent_id] = (px, py)

            contagion = self.irony.get_agent_contagion_status(
                ag.agent_id,
                branch_ref=branch_ref,
                query_tick=head_tick,
                focus_fact_id=focus_fact_id,
            )
            beliefs = self.vault.get_agent_beliefs(
                ag.agent_id, branch_ref=branch_ref, query_tick=head_tick
            )
            secrets = [
                f"{b.subject} {b.predicate} {b.obj}"
                for b in beliefs.values()
                if b.is_secret or b.stance == "WITHHOLDS_SECRET"
            ]
            believed_lies = [
                f"{b.subject} {b.predicate} {b.obj}"
                for b in beliefs.values()
                if not b.objective_truth and b.stance == "BELIEVES_TRUE"
            ]

            # Determine procedural facial expression
            if st["vital_status"] == "DEAD":
                expr = "DEAD"
            elif ag.agent_id == active_actor and active_type == "LIE":
                expr = "LYING_SWEAT"
            elif ag.agent_id in active_targets and active_type in ("LIE", "TELL"):
                # Check if target caught a lie at this tick
                caught = any(
                    b.tick == head_tick and b.predicate == "lied_about" for b in beliefs.values()
                )
                expr = "SHOCK" if caught else ("SUSPICIOUS" if believed_lies else "NEUTRAL")
            elif secrets:
                expr = "SCHEMING"
            else:
                expr = "NEUTRAL"

            public_line = ""
            if ag.agent_id == active_actor and (active_raw or active_summary):
                public_line = active_raw or active_summary

            if secrets:
                god_thought = f"🤫 HIDING SECRET: {secrets[0]}"
            elif believed_lies:
                god_thought = f"🔴 BELIEVES LIE: {believed_lies[0]}"
            elif ag.secret_agenda:
                god_thought = f"🎯 AGENDA: {ag.secret_agenda}"
            else:
                god_thought = "Observing scene"

            held = self.inventory.get_agent_held_items(
                ag.agent_id, branch_ref=branch_ref, query_tick=head_tick
            )
            pitch, rate = self._voice_profile(ag.agent_id)

            puppets.append(
                PuppetKeyframe(
                    agent_id=ag.agent_id,
                    name=ag.name,
                    role=ag.role,
                    location_id=lid,
                    x=px,
                    y=py,
                    expression=expr,
                    contagion_color=str(contagion["color"]),
                    held_items=tuple(f"{i.icon} {i.name}" for i in held),
                    public_speech=public_line,
                    god_mode_thought=god_thought,
                    composure=85.0 if expr == "LYING_SWEAT" else 100.0,
                    voice_pitch=pitch,
                    voice_rate=rate,
                )
            )

        earshot_rings: list[EarshotRingKeyframe] = []
        if active_actor in agent_coords and active_type in ("TELL", "LIE", "EAVESDROP", "WITNESS_ACTION"):
            ax, ay = agent_coords[active_actor]
            radius_px = 68.0 if active_vis == "WHISPER" else 135.0
            if active_type == "LIE":
                rtype = "LIE_CRIMSON"
                rlabel = "Fabricated Lie (Whisper)" if active_vis == "WHISPER" else "Fabricated Lie"
            elif active_type == "EAVESDROP":
                rtype = "EAVESDROP_GOLD"
                rlabel = "Doorway Eavesdrop Cone"
            else:
                rtype = "HONEST_CYAN"
                rlabel = "Earshot Radius"
            earshot_rings.append(
                EarshotRingKeyframe(
                    speaker_id=active_actor,
                    x=ax,
                    y=ay,
                    radius_px=radius_px,
                    ring_type=rtype,
                    label=rlabel,
                )
            )

        item_arcs: list[ItemArcKeyframe] = []
        if active_item_id and active_actor in agent_coords and active_targets:
            target_id = str(active_targets[0])
            if target_id in agent_coords:
                x0, y0 = agent_coords[active_actor]
                x1, y1 = agent_coords[target_id]
                item_obj = self.inventory.get_item(str(active_item_id))
                pts = tuple(
                    rust_parabolic_item_arc(x0, y0, x1, y1, 42.0, step / 10.0)
                    for step in range(11)
                )
                item_arcs.append(
                    ItemArcKeyframe(
                        item_id=str(active_item_id),
                        item_name=item_obj.name if item_obj else str(active_item_id),
                        icon=item_obj.icon if item_obj else "🗡️",
                        from_x=x0,
                        from_y=y0,
                        to_x=x1,
                        to_y=y1,
                        arc_points=pts,
                    )
                )

        irony_score = self.irony.compute_scene_irony(
            [a.agent_id for a in all_agents], branch_ref=branch_ref, query_tick=head_tick
        )

        return StageFrame(
            branch_id=self.db.resolve_branch_id(branch_ref),
            tick=head_tick,
            story_time=format_minutes_to_story_time(story_mins),
            event_id=active_event_id,
            headline=active_summary,
            dramatic_irony_score=round(irony_score, 4),
            puppets=tuple(puppets),
            earshot_rings=tuple(earshot_rings),
            item_arcs=tuple(item_arcs),
        )
