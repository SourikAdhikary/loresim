"""Counterfactual 'Butterfly Effect' Causal & Epistemic Blast-Radius Analyzer."""

from __future__ import annotations

import json

from loresim.core.hashing import compute_fact_id
from loresim.core.types import BlastRadiusItem, WorldEvent
from loresim.storage.db import SQLiteDatabase


class ButterflyAnalyzer:
    """Traces the downstream causal and epistemic blast radius when a historical event is disabled."""

    def __init__(self, db: SQLiteDatabase) -> None:
        self.db = db

    def load_branch_events(
        self, branch_ref: str = "main", up_to_tick: int | None = None
    ) -> list[WorldEvent]:
        where_sql, params = self.db.build_bitemporal_sql_Clause(branch_ref, up_to_tick)
        rows = self.db.fetchall(
            f"SELECT * FROM world_events WHERE {where_sql} ORDER BY tick ASC, rowid ASC",
            params,
        )
        return [
            WorldEvent(
                event_id=str(r["event_id"]),
                branch_id=str(r["branch_id"]),
                tick=int(r["tick"]),
                story_time_minutes=int(r["story_time_minutes"]),
                chapter_ref=str(r["chapter_ref"]),
                event_type=str(r["event_type"]),
                location_id=str(r["location_id"]),
                actor_id=str(r["actor_id"]),
                target_ids=tuple(json.loads(str(r["target_ids_json"]))),
                visibility=str(r["visibility"]),
                summary=str(r["summary"]),
                raw_text=str(r["raw_text"]),
                claims=tuple(json.loads(str(r["claims_json"]))),
                item_id=r["item_id"],
                preconditions=json.loads(str(r["preconditions_json"])),
            )
            for r in rows
        ]

    def compute_blast_radius(
        self,
        disabled_event_id: str,
        branch_ref: str = "main",
    ) -> list[BlastRadiusItem]:
        """Replay the narrative event DAG with `disabled_event_id` removed and identify every
        downstream event that becomes causally or epistemically impossible.
        """
        events = self.load_branch_events(branch_ref=branch_ref)
        target_idx = next(
            (i for i, ev in enumerate(events) if ev.event_id == disabled_event_id),
            None,
        )
        if target_idx is None:
            return []

        # Shadow state simulation without `disabled_event_id` (and without any cascading broken events)
        agent_locs: dict[str, str] = {}
        agent_vital: dict[str, str] = {}
        item_holders: dict[str, str] = {}
        agent_known_facts: dict[str, set[str]] = {}
        fact_origin_event: dict[str, str] = {}
        item_origin_event: dict[str, str] = {}
        loc_origin_event: dict[str, str] = {}
        broken_events: dict[str, BlastRadiusItem] = {}

        # Seed initial agent locations and item holders from tick 0
        for r in self.db.fetchall("SELECT agent_id, location_id, vital_status FROM agent_states WHERE tick = 0"):
            aid = str(r["agent_id"])
            agent_locs[aid] = str(r["location_id"])
            agent_vital[aid] = str(r["vital_status"])
        for r in self.db.fetchall("SELECT item_id, holder_id FROM item_ledger WHERE tick = 0"):
            item_holders[str(r["item_id"])] = str(r["holder_id"])

        for idx, ev in enumerate(events):
            if idx == target_idx:
                # Record facts/items/moves that `disabled_event_id` would have produced so we can trace chains
                for cl in ev.claims:
                    fid = compute_fact_id(
                        str(cl.get("subject", "")),
                        str(cl.get("predicate", "")),
                        str(cl.get("object", "")),
                        not (ev.event_type == "LIE"),
                    )
                    fact_origin_event[fid] = ev.event_id
                if ev.item_id:
                    item_origin_event[ev.item_id] = ev.event_id
                if ev.event_type == "MOVE":
                    loc_origin_event[ev.actor_id] = ev.event_id
                continue

            # If after `target_idx`, check if any precondition of `ev` fails in the counterfactual shadow world!
            if idx > target_idx:
                broken_reason: str | None = None
                parent_cause: str = disabled_event_id

                # 1. Explicit causal parent event dependency
                req_events = ev.preconditions.get("requires_events", [])
                for req_ev_id in req_events:
                    if req_ev_id == disabled_event_id or req_ev_id in broken_events:
                        broken_reason = f"Depends on disabled/broken event '{req_ev_id}'"
                        parent_cause = req_ev_id
                        break

                # 2. Epistemic fact dependency
                if broken_reason is None:
                    req_facts = ev.preconditions.get("requires_facts", [])
                    known = agent_known_facts.get(ev.actor_id, set())
                    for rf in req_facts:
                        if rf not in known:
                            broken_reason = f"Actor '{ev.actor_id}' never learned required fact '{rf}'"
                            parent_cause = fact_origin_event.get(rf, disabled_event_id)
                            break

                # 3. Item ownership dependency
                if broken_reason is None and ev.item_id and ev.event_type in ("GIVE_ITEM", "USE_ITEM", "DROP_ITEM"):
                    if item_holders.get(ev.item_id) != ev.actor_id:
                        broken_reason = (
                            f"Actor '{ev.actor_id}' does not hold item '{ev.item_id}' "
                            f"(currently held by '{item_holders.get(ev.item_id, 'nobody')}')"
                        )
                        parent_cause = item_origin_event.get(ev.item_id, disabled_event_id)

                # 4. Location occupancy dependency (if event isn't a MOVE and requires actor at `ev.location_id`)
                if (
                    broken_reason is None
                    and ev.event_type != "MOVE"
                    and ev.preconditions.get("enforce_location", False)
                ):
                    if agent_locs.get(ev.actor_id) != ev.location_id:
                        broken_reason = (
                            f"Actor '{ev.actor_id}' is at '{agent_locs.get(ev.actor_id)}', "
                            f"not '{ev.location_id}'"
                        )
                        parent_cause = loc_origin_event.get(ev.actor_id, disabled_event_id)

                if broken_reason is not None:
                    prior_chain = (
                        broken_events[parent_cause].causal_chain
                        if parent_cause in broken_events
                        else (disabled_event_id,)
                    )
                    chain = (*prior_chain, ev.event_id)
                    broken_events[ev.event_id] = BlastRadiusItem(
                        broken_event_id=ev.event_id,
                        tick=ev.tick,
                        actor_id=ev.actor_id,
                        summary=ev.summary,
                        broken_reason=broken_reason,
                        causal_chain=chain,
                    )
                    # Record what this broken event would have produced for further cascade tracking
                    for cl in ev.claims:
                        fid = compute_fact_id(
                            str(cl.get("subject", "")),
                            str(cl.get("predicate", "")),
                            str(cl.get("object", "")),
                            not (ev.event_type == "LIE"),
                        )
                        fact_origin_event.setdefault(fid, ev.event_id)
                    if ev.item_id:
                        item_origin_event.setdefault(ev.item_id, ev.event_id)
                    if ev.event_type == "MOVE":
                        loc_origin_event.setdefault(ev.actor_id, ev.event_id)
                    continue

            # Event succeeded in shadow world: apply its effects!
            agent_locs[ev.actor_id] = ev.location_id
            if ev.event_type == "DEATH":
                target = ev.target_ids[0] if ev.target_ids else ev.actor_id
                agent_vital[target] = "DEAD"
            if ev.item_id:
                if ev.event_type == "TAKE_ITEM":
                    item_holders[ev.item_id] = ev.actor_id
                elif ev.event_type == "GIVE_ITEM" and ev.target_ids:
                    item_holders[ev.item_id] = ev.target_ids[0]
                elif ev.event_type == "DROP_ITEM":
                    item_holders[ev.item_id] = ev.location_id
            for cl in ev.claims:
                fid = compute_fact_id(
                    str(cl.get("subject", "")),
                    str(cl.get("predicate", "")),
                    str(cl.get("object", "")),
                    not (ev.event_type == "LIE"),
                )
                recipients = [ev.actor_id, *ev.target_ids]
                if ev.visibility == "PUBLIC_HERE":
                    for aid, loc in agent_locs.items():
                        if loc == ev.location_id and agent_vital.get(aid, "ALIVE") == "ALIVE":
                            recipients.append(aid)
                for rid in set(recipients):
                    agent_known_facts.setdefault(rid, set()).add(fid)

        return list(broken_events.values())
