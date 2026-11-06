"""Bi-temporal per-agent EpistemicVault B_a(b, t) and canonical proposition store."""

from __future__ import annotations

import uuid

from loresim.core.hashing import compute_fact_id
from loresim.core.types import CanonicalFact, EpistemicBelief
from loresim.storage.db import SQLiteDatabase


class EpistemicVault:
    """Manages canonical propositions and per-character epistemic belief graphs across `(branch, tick)`."""

    def __init__(self, db: SQLiteDatabase) -> None:
        self.db = db

    def upsert_canonical_fact(
        self,
        subject: str,
        predicate: str,
        obj: str,
        objective_truth: bool = True,
        created_tick: int = 0,
        origin_event_id: str = "",
        importance: float = 1.0,
        branch_ref: str = "main",
        fact_id: str | None = None,
    ) -> CanonicalFact:
        branch_id = self.db.resolve_branch_id(branch_ref)
        fid = fact_id or compute_fact_id(subject, predicate, obj, objective_truth)
        fact = CanonicalFact(
            fact_id=fid,
            branch_id=branch_id,
            created_tick=int(created_tick),
            subject=subject.strip(),
            predicate=predicate.strip(),
            obj=obj.strip(),
            objective_truth=bool(objective_truth),
            origin_event_id=origin_event_id,
            importance=float(importance),
        )
        existing = self.db.fetchone("SELECT * FROM canonical_facts WHERE fact_id = ?", (fid,))
        if existing is not None:
            return CanonicalFact(
                fact_id=str(existing["fact_id"]),
                branch_id=str(existing["branch_id"]),
                created_tick=int(existing["created_tick"]),
                subject=str(existing["subject"]),
                predicate=str(existing["predicate"]),
                obj=str(existing["object"]),
                objective_truth=bool(existing["objective_truth"]),
                origin_event_id=str(existing["origin_event_id"]),
                importance=float(existing["importance"]),
                invalidated_tick=existing["invalidated_tick"],
            )
        self.db.execute(
            """
            INSERT INTO canonical_facts
            (fact_id, branch_id, created_tick, invalidated_tick, subject, predicate, object,
             objective_truth, origin_event_id, importance)
            VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)
            """,
            (
                fact.fact_id,
                fact.branch_id,
                fact.created_tick,
                fact.subject,
                fact.predicate,
                fact.obj,
                1 if fact.objective_truth else 0,
                fact.origin_event_id,
                fact.importance,
            ),
        )
        summary = f"{fact.subject} {fact.predicate} {fact.obj}"
        self.db.execute(
            "INSERT INTO facts_fts (fact_id, subject, predicate, object, summary) VALUES (?, ?, ?, ?, ?)",
            (fact.fact_id, fact.subject, fact.predicate, fact.obj, summary),
        )
        return fact

    def get_fact(self, fact_id: str) -> CanonicalFact | None:
        row = self.db.fetchone("SELECT * FROM canonical_facts WHERE fact_id = ?", (fact_id,))
        if row is None:
            return None
        return CanonicalFact(
            fact_id=str(row["fact_id"]),
            branch_id=str(row["branch_id"]),
            created_tick=int(row["created_tick"]),
            subject=str(row["subject"]),
            predicate=str(row["predicate"]),
            obj=str(row["object"]),
            objective_truth=bool(row["objective_truth"]),
            origin_event_id=str(row["origin_event_id"]),
            importance=float(row["importance"]),
            invalidated_tick=row["invalidated_tick"],
        )

    def list_visible_facts(
        self, branch_ref: str = "main", query_tick: int | None = None
    ) -> list[CanonicalFact]:
        bounds = self.db.get_branch_ancestry_bounds(branch_ref, query_tick)
        facts: dict[str, CanonicalFact] = {}
        for b_id, cap_tick in bounds:
            rows = self.db.fetchall(
                """
                SELECT * FROM canonical_facts
                WHERE branch_id = ? AND created_tick <= ?
                ORDER BY created_tick ASC, rowid ASC
                """,
                (b_id, cap_tick),
            )
            for r in rows:
                facts[str(r["fact_id"])] = CanonicalFact(
                    fact_id=str(r["fact_id"]),
                    branch_id=str(r["branch_id"]),
                    created_tick=int(r["created_tick"]),
                    subject=str(r["subject"]),
                    predicate=str(r["predicate"]),
                    obj=str(r["object"]),
                    objective_truth=bool(r["objective_truth"]),
                    origin_event_id=str(r["origin_event_id"]),
                    importance=float(r["importance"]),
                    invalidated_tick=r["invalidated_tick"],
                )
        return list(facts.values())

    def record_belief(
        self,
        agent_id: str,
        fact_id: str,
        stance: str,
        confidence: float,
        modality: str,
        source_agent_id: str,
        acquired_event_id: str,
        tick: int,
        is_secret: bool = False,
        branch_ref: str = "main",
    ) -> EpistemicBelief:
        branch_id = self.db.resolve_branch_id(branch_ref)
        belief_id = f"bel_{uuid.uuid4().hex[:12]}"
        clamped_conf = max(0.0, min(1.0, float(confidence)))
        self.db.execute(
            """
            INSERT INTO epistemic_beliefs
            (belief_id, branch_id, tick, agent_id, fact_id, stance, confidence,
             modality, source_agent_id, acquired_event_id, is_secret)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                belief_id,
                branch_id,
                int(tick),
                agent_id,
                fact_id,
                stance,
                clamped_conf,
                modality,
                source_agent_id,
                acquired_event_id,
                1 if is_secret else 0,
            ),
        )
        fact = self.get_fact(fact_id)
        return EpistemicBelief(
            belief_id=belief_id,
            branch_id=branch_id,
            tick=int(tick),
            agent_id=agent_id,
            fact_id=fact_id,
            stance=stance,
            confidence=clamped_conf,
            modality=modality,
            source_agent_id=source_agent_id,
            acquired_event_id=acquired_event_id,
            is_secret=is_secret,
            subject=fact.subject if fact else "",
            predicate=fact.predicate if fact else "",
            obj=fact.obj if fact else "",
            objective_truth=fact.objective_truth if fact else True,
        )

    def get_agent_beliefs(
        self, agent_id: str, branch_ref: str = "main", query_tick: int | None = None
    ) -> dict[str, EpistemicBelief]:
        """Return the latest belief state per `fact_id` for `agent_id` at `(branch_ref, query_tick)`."""
        bounds = self.db.get_branch_ancestry_bounds(branch_ref, query_tick)
        latest: dict[str, EpistemicBelief] = {}
        for b_id, cap_tick in bounds:
            rows = self.db.fetchall(
                """
                SELECT b.*, f.subject, f.predicate, f.object, f.objective_truth
                FROM epistemic_beliefs b
                JOIN canonical_facts f ON b.fact_id = f.fact_id
                WHERE b.branch_id = ? AND b.agent_id = ? AND b.tick <= ?
                ORDER BY b.tick ASC, b.rowid ASC
                """,
                (b_id, agent_id, cap_tick),
            )
            for r in rows:
                fid = str(r["fact_id"])
                latest[fid] = EpistemicBelief(
                    belief_id=str(r["belief_id"]),
                    branch_id=str(r["branch_id"]),
                    tick=int(r["tick"]),
                    agent_id=str(r["agent_id"]),
                    fact_id=fid,
                    stance=str(r["stance"]),
                    confidence=float(r["confidence"]),
                    modality=str(r["modality"]),
                    source_agent_id=str(r["source_agent_id"]),
                    acquired_event_id=str(r["acquired_event_id"]),
                    is_secret=bool(r["is_secret"]),
                    subject=str(r["subject"]),
                    predicate=str(r["predicate"]),
                    obj=str(r["object"]),
                    objective_truth=bool(r["objective_truth"]),
                )
        return latest

    def get_agent_belief_for_fact(
        self,
        agent_id: str,
        fact_id: str,
        branch_ref: str = "main",
        query_tick: int | None = None,
    ) -> EpistemicBelief | None:
        return self.get_agent_beliefs(agent_id, branch_ref=branch_ref, query_tick=query_tick).get(fact_id)

    def find_contradicting_firsthand_belief(
        self,
        agent_id: str,
        subject: str,
        predicate: str,
        claimed_obj: str,
        branch_ref: str = "main",
        query_tick: int | None = None,
    ) -> EpistemicBelief | None:
        """Check if `agent_id` holds a FIRSTHAND belief on `(subject, predicate)` with a different object
        OR holds a FIRSTHAND belief that the exact `(subject, predicate, claimed_obj)` is false/secretly done by another.
        """
        beliefs = self.get_agent_beliefs(agent_id, branch_ref=branch_ref, query_tick=query_tick)
        norm_s = subject.strip().lower()
        norm_p = predicate.strip().lower()
        norm_o = claimed_obj.strip().lower()
        for bel in beliefs.values():
            if bel.modality != "FIRSTHAND" or bel.confidence < 0.9:
                continue
            # Case 1: Same subject & predicate, different object (e.g., "treaty status = burned" vs "stolen")
            if bel.subject.lower() == norm_s and bel.predicate.lower() == norm_p and bel.obj.lower() != norm_o:
                return bel
            # Case 2: Same predicate & object, different subject for an exclusive action (e.g. "Vance burned treaty" vs "Rebels burned/stole treaty")
            if bel.obj.lower() == norm_o and bel.subject.lower() != norm_s:
                return bel
        return None
