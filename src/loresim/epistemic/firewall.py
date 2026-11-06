"""Zero-Leak EpistemicPromptFirewall and post-generation omniscient leak verifier."""

from __future__ import annotations

from typing import Any

from loresim.core.errors import EpistemicLeakTrap
from loresim.epistemic.vault import EpistemicVault
from loresim.world.agents import AgentRegistry
from loresim.world.inventory import InventoryTracker


class EpistemicPromptFirewall:
    """Compiles character prompts strictly from their private EpistemicVault B_a(b, t)
    and verifies generated dialogue/actions against unlearned canonical secrets.
    """

    def __init__(
        self,
        vault: EpistemicVault,
        agents: AgentRegistry,
        inventory: InventoryTracker,
    ) -> None:
        self.vault = vault
        self.agents = agents
        self.inventory = inventory

    def compile_agent_context(
        self,
        agent_id: str,
        branch_ref: str = "main",
        query_tick: int | None = None,
    ) -> dict[str, Any]:
        """Compile the strictly partitioned epistemic context for `agent_id` at `(branch_ref, query_tick)`."""
        profile = self.agents.get_agent(agent_id)
        state = self.agents.get_agent_state(agent_id, branch_ref=branch_ref, query_tick=query_tick)
        held_items = self.inventory.get_agent_held_items(
            agent_id, branch_ref=branch_ref, query_tick=query_tick
        )
        beliefs_map = self.vault.get_agent_beliefs(
            agent_id, branch_ref=branch_ref, query_tick=query_tick
        )

        known_truths: list[str] = []
        believed_falsehoods: list[str] = []
        withheld_secrets: list[str] = []
        rejected_lies: list[str] = []

        for bel in beliefs_map.values():
            statement = f"{bel.subject} {bel.predicate} {bel.obj}"
            if bel.stance == "WITHHOLDS_SECRET" or bel.is_secret:
                if bel.stance == "BELIEVES_FALSE":
                    withheld_secrets.append(f"[COVER LIE YOU TOLD]: {statement}")
                else:
                    withheld_secrets.append(f"[SECRET YOU ARE HIDING]: {statement}")
            elif bel.stance == "BELIEVES_TRUE":
                if bel.objective_truth:
                    known_truths.append(f"{statement} (conf={bel.confidence:.2f}, via={bel.modality})")
                else:
                    # The character genuinely believes this falsehood is true!
                    believed_falsehoods.append(
                        f"{statement} (conf={bel.confidence:.2f}, told by {bel.source_agent_id})"
                    )
            elif bel.stance == "BELIEVES_FALSE":
                rejected_lies.append(f"FALSE CLAIM REJECTED: {statement} (claimed by {bel.source_agent_id})")

        prompt_lines = [
            f"=== EPISTEMIC SANDBOX FOR CHARACTER: {profile.name if profile else agent_id} ===",
            f"Role: {profile.role if profile else 'Unknown'} | Location: {state['location_id']} | Vital: {state['vital_status']}",
            f"Held Items: {[i.name for i in held_items]}",
        ]
        if profile and profile.secret_agenda:
            prompt_lines.append(f"Private Agenda: {profile.secret_agenda}")
        if withheld_secrets:
            prompt_lines.append("Secrets You Know (DO NOT REVEAL UNLESS FORCED):")
            prompt_lines.extend(f"  - {s}" for s in withheld_secrets)
        if known_truths or believed_falsehoods:
            prompt_lines.append("Facts You Believe to Be True:")
            for item in known_truths + believed_falsehoods:
                prompt_lines.append(f"  - {item}")
        if rejected_lies:
            prompt_lines.append("Lies You Caught Others Telling:")
            for item in rejected_lies:
                prompt_lines.append(f"  - {item}")

        prompt_text = "\n".join(prompt_lines)
        return {
            "agent_id": agent_id,
            "tick": query_tick,
            "location_id": state["location_id"],
            "held_items": [i.item_id for i in held_items],
            "known_fact_ids": set(beliefs_map.keys()),
            "known_truths": known_truths,
            "believed_falsehoods": believed_falsehoods,
            "withheld_secrets": withheld_secrets,
            "rejected_lies": rejected_lies,
            "prompt_text": prompt_text,
            "token_estimate": max(1, len(prompt_text.split())),
        }

    def audit_utterance_for_leaks(
        self,
        agent_id: str,
        utterance: str,
        branch_ref: str = "main",
        query_tick: int | None = None,
        raise_on_leak: bool = False,
    ) -> list[dict[str, Any]]:
        """Verify that `utterance` by `agent_id` does not reference canonical facts unknown to `agent_id`."""
        agent_beliefs = self.vault.get_agent_beliefs(
            agent_id, branch_ref=branch_ref, query_tick=query_tick
        )
        all_visible_facts = self.vault.list_visible_facts(
            branch_ref=branch_ref, query_tick=query_tick
        )
        lower_utt = utterance.lower()
        leaks: list[dict[str, Any]] = []

        for fact in all_visible_facts:
            if fact.fact_id in agent_beliefs and agent_beliefs[fact.fact_id].confidence > 0.0:
                continue
            # Check if the utterance explicitly leaks both the predicate and exact object identifier
            pred_str = fact.predicate.strip().lower()
            obj_str = fact.obj.strip().lower()
            if pred_str and obj_str and pred_str in lower_utt and obj_str in lower_utt:
                leaks.append(
                    {
                        "agent_id": agent_id,
                        "leaked_fact_id": fact.fact_id,
                        "proposition": f"{fact.subject} {fact.predicate} {fact.obj}",
                        "origin_tick": fact.created_tick,
                    }
                )

        if leaks and raise_on_leak:
            first = leaks[0]
            raise EpistemicLeakTrap(
                f"EpistemicLeakTrap: Agent '{agent_id}' leaked unknown fact '{first['proposition']}' ({first['leaked_fact_id']})"
            )
        return leaks
