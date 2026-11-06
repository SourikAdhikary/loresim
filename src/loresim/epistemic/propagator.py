"""Dynamic Epistemic Logic (DEL) action models: WITNESS, TELL, LIE, EAVESDROP & Lie Exposure."""

from __future__ import annotations

from typing import Any

from loresim.core.rust_bridge import (
    rust_apply_lie_exposure_penalty,
    rust_log_odds_belief_update,
)
from loresim.core.types import EpistemicBelief
from loresim.epistemic.vault import EpistemicVault
from loresim.storage.db import SQLiteDatabase
from loresim.world.agents import AgentRegistry


class EpistemicPropagator:
    """Propagates knowledge, hearsay rumors, and deliberate lies across the social graph."""

    def __init__(
        self,
        db: SQLiteDatabase,
        vault: EpistemicVault,
        agents: AgentRegistry,
    ) -> None:
        self.db = db
        self.vault = vault
        self.agents = agents

    def propagate_witness(
        self,
        witness_ids: list[str],
        subject: str,
        predicate: str,
        obj: str,
        tick: int,
        event_id: str,
        is_secret: bool = False,
        importance: float = 1.0,
        branch_ref: str = "main",
    ) -> list[EpistemicBelief]:
        """Grant `FIRSTHAND` (`c = 1.0`) knowledge of an objective event to all witnesses."""
        fact = self.vault.upsert_canonical_fact(
            subject=subject,
            predicate=predicate,
            obj=obj,
            objective_truth=True,
            created_tick=tick,
            origin_event_id=event_id,
            importance=importance,
            branch_ref=branch_ref,
        )
        created: list[EpistemicBelief] = []
        stance = "WITHHOLDS_SECRET" if is_secret else "BELIEVES_TRUE"
        for wid in witness_ids:
            bel = self.vault.record_belief(
                agent_id=wid,
                fact_id=fact.fact_id,
                stance=stance,
                confidence=1.0,
                modality="FIRSTHAND",
                source_agent_id=wid,
                acquired_event_id=event_id,
                tick=tick,
                is_secret=is_secret,
                branch_ref=branch_ref,
            )
            created.append(bel)
        return created

    def propagate_testimony(
        self,
        speaker_id: str,
        listener_ids: list[str],
        subject: str,
        predicate: str,
        obj: str,
        tick: int,
        event_id: str,
        is_lie: bool = False,
        modality: str = "HEARSAY",
        importance: float = 1.0,
        branch_ref: str = "main",
    ) -> dict[str, Any]:
        """Propagate an honest testimony (`TELL`) or deliberate fabrication (`LIE`) to `listener_ids`.

        Automatically triggers **Firsthand Lie Exposure** if a listener already witnessed
        contradictory reality firsthand!
        """
        fact = self.vault.upsert_canonical_fact(
            subject=subject,
            predicate=predicate,
            obj=obj,
            objective_truth=not is_lie,
            created_tick=tick,
            origin_event_id=event_id,
            importance=importance,
            branch_ref=branch_ref,
        )
        # If speaker is lying, record that the speaker themselves knows this claim is FALSE (`BELIEVES_FALSE`)
        if is_lie:
            self.vault.record_belief(
                agent_id=speaker_id,
                fact_id=fact.fact_id,
                stance="BELIEVES_FALSE",
                confidence=1.0,
                modality="FIRSTHAND",
                source_agent_id=speaker_id,
                acquired_event_id=event_id,
                tick=tick,
                is_secret=True,
                branch_ref=branch_ref,
            )

        updated_beliefs: list[EpistemicBelief] = []
        exposed_to: list[dict[str, Any]] = []

        for lid in listener_ids:
            if lid == speaker_id:
                continue
            contradiction = self.vault.find_contradicting_firsthand_belief(
                agent_id=lid,
                subject=subject,
                predicate=predicate,
                claimed_obj=obj,
                branch_ref=branch_ref,
                query_tick=tick,
            )
            current_trust = self.agents.get_trust(lid, speaker_id, branch_ref=branch_ref, query_tick=tick)

            if contradiction is not None:
                # Listener immediately catches the speaker in a lie!
                new_trust = rust_apply_lie_exposure_penalty(current_trust, 0.70)
                self.agents.set_relationship(
                    from_agent_id=lid,
                    to_agent_id=speaker_id,
                    trust=new_trust,
                    relation_label="Caught Lying",
                    tick=tick,
                    branch_ref=branch_ref,
                )
                bel = self.vault.record_belief(
                    agent_id=lid,
                    fact_id=fact.fact_id,
                    stance="BELIEVES_FALSE",
                    confidence=1.0,
                    modality="FIRSTHAND",
                    source_agent_id=speaker_id,
                    acquired_event_id=event_id,
                    tick=tick,
                    is_secret=False,
                    branch_ref=branch_ref,
                )
                # Also record explicit meta-fact that `lid` caught `speaker_id` lying
                lie_meta = self.vault.upsert_canonical_fact(
                    subject=speaker_id,
                    predicate="lied_about",
                    obj=f"{subject} {predicate} {obj}",
                    objective_truth=True,
                    created_tick=tick,
                    origin_event_id=event_id,
                    branch_ref=branch_ref,
                )
                self.vault.record_belief(
                    agent_id=lid,
                    fact_id=lie_meta.fact_id,
                    stance="BELIEVES_TRUE",
                    confidence=1.0,
                    modality="FIRSTHAND",
                    source_agent_id=speaker_id,
                    acquired_event_id=event_id,
                    tick=tick,
                    branch_ref=branch_ref,
                )
                updated_beliefs.append(bel)
                exposed_to.append(
                    {
                        "listener_id": lid,
                        "speaker_id": speaker_id,
                        "contradicting_fact_id": contradiction.fact_id,
                        "old_trust": current_trust,
                        "new_trust": new_trust,
                    }
                )
            else:
                prior_bel = self.vault.get_agent_belief_for_fact(
                    lid, fact.fact_id, branch_ref=branch_ref, query_tick=tick
                )
                prior_conf = prior_bel.confidence if prior_bel is not None else 0.50
                new_conf = rust_log_odds_belief_update(
                    prior_conf=prior_conf,
                    trust_in_speaker=current_trust,
                    speaker_asserted_conf=0.95,
                    coupling_k=2.4,
                )
                stance = "BELIEVES_TRUE" if new_conf >= 0.55 else "SUSPECTS"
                eff_modality = "DECEIVED" if is_lie and stance == "BELIEVES_TRUE" else modality
                bel = self.vault.record_belief(
                    agent_id=lid,
                    fact_id=fact.fact_id,
                    stance=stance,
                    confidence=new_conf,
                    modality=eff_modality,
                    source_agent_id=speaker_id,
                    acquired_event_id=event_id,
                    tick=tick,
                    is_secret=False,
                    branch_ref=branch_ref,
                )
                updated_beliefs.append(bel)

        return {
            "fact": fact,
            "updated_beliefs": updated_beliefs,
            "lie_exposures": exposed_to,
        }
