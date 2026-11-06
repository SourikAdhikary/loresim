"""Dramatic Irony Analyzer (I_irony) and Rumor/Lie Contagion Map classifier."""

from __future__ import annotations

from typing import Any

from loresim.core.rust_bridge import rust_compute_dramatic_irony
from loresim.epistemic.vault import EpistemicVault
from loresim.world.agents import AgentRegistry


class DramaticIronyAnalyzer:
    """Computes scene dramatic irony scores and classifies character contagion states."""

    def __init__(self, vault: EpistemicVault, agents: AgentRegistry) -> None:
        self.vault = vault
        self.agents = agents

    def compute_scene_irony(
        self,
        participant_ids: list[str],
        branch_ref: str = "main",
        query_tick: int | None = None,
    ) -> float:
        """Compute normalized Dramatic Irony score I_irony in [0.0, 1.0] across scene participants."""
        facts = self.vault.list_visible_facts(branch_ref=branch_ref, query_tick=query_tick)
        if not facts or not participant_ids:
            return 0.0

        truths: list[float] = []
        beliefs: list[float] = []
        weights: list[float] = []

        for aid in participant_ids:
            agent_bels = self.vault.get_agent_beliefs(
                aid, branch_ref=branch_ref, query_tick=query_tick
            )
            for fact in facts:
                t_val = 1.0 if fact.objective_truth else -1.0
                bel = agent_bels.get(fact.fact_id)
                if bel is None:
                    b_val = 0.0
                elif bel.stance == "BELIEVES_TRUE":
                    b_val = bel.confidence
                elif bel.stance == "BELIEVES_FALSE":
                    b_val = -bel.confidence
                elif bel.stance == "WITHHOLDS_SECRET":
                    b_val = bel.confidence if fact.objective_truth else -bel.confidence
                else:
                    b_val = 0.0
                truths.append(t_val)
                beliefs.append(b_val)
                weights.append(fact.importance)

        return rust_compute_dramatic_irony(truths, beliefs, weights)

    def get_agent_contagion_status(
        self,
        agent_id: str,
        branch_ref: str = "main",
        query_tick: int | None = None,
        focus_fact_id: str | None = None,
    ) -> dict[str, Any]:
        """Classify an agent's epistemic contagion color for the Studio Contagion Map:
        - `GOLD_DECEIVER`: Withholding a secret or actively propagating a lie.
        - `RED_LIE`: Believes a fabricated falsehood (`objective_truth == False` and `stance == BELIEVES_TRUE`).
        - `BLUE_TRUTH`: Knows objective truth (`objective_truth == True` and `stance == BELIEVES_TRUE`).
        - `GREY_UNAWARE`: Unaware of focus facts.
        """
        beliefs = self.vault.get_agent_beliefs(
            agent_id, branch_ref=branch_ref, query_tick=query_tick
        )
        if focus_fact_id is not None:
            bel = beliefs.get(focus_fact_id)
            if bel is None:
                return {"color": "GREY_UNAWARE", "label": "Unaware", "confidence": 0.0}
            if bel.is_secret or bel.stance == "WITHHOLDS_SECRET":
                return {"color": "GOLD_DECEIVER", "label": "Hiding Secret / Deceiver", "confidence": bel.confidence}
            if not bel.objective_truth and bel.stance == "BELIEVES_TRUE":
                return {"color": "RED_LIE", "label": "Believes Lie", "confidence": bel.confidence}
            if bel.objective_truth and bel.stance == "BELIEVES_TRUE":
                return {"color": "BLUE_TRUTH", "label": "Knows Truth", "confidence": bel.confidence}
            return {"color": "BLUE_TRUTH", "label": "Rejected Lie", "confidence": bel.confidence}

        # Aggregate status across all beliefs at `query_tick`
        has_secret = any(b.is_secret or b.stance == "WITHHOLDS_SECRET" for b in beliefs.values())
        if has_secret:
            return {"color": "GOLD_DECEIVER", "label": "Active Deceiver / Secret Holder", "confidence": 1.0}
        deceived = [b for b in beliefs.values() if not b.objective_truth and b.stance == "BELIEVES_TRUE"]
        if deceived:
            return {"color": "RED_LIE", "label": f"Deceived ({len(deceived)} lies)", "confidence": deceived[0].confidence}
        truths = [b for b in beliefs.values() if b.objective_truth and b.stance == "BELIEVES_TRUE"]
        if truths:
            return {"color": "BLUE_TRUTH", "label": f"Informed ({len(truths)} facts)", "confidence": truths[0].confidence}
        return {"color": "GREY_UNAWARE", "label": "Unaware", "confidence": 0.0}
