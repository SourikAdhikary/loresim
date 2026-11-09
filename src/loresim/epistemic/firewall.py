"""Zero-Leak EpistemicPromptFirewall and alias/paraphrase-aware omniscient leak verifier."""

from __future__ import annotations

from typing import Any

from loresim.core.errors import EpistemicLeakTrap
from loresim.epistemic.vault import EpistemicVault
from loresim.world.agents import AgentRegistry
from loresim.world.inventory import InventoryTracker

_PREDICATE_SYNONYM_CLUSTERS: tuple[tuple[str, ...], ...] = (
    ("burned", "burn", "burnt", "incinerated", "torched", "set fire to", "destroyed in the flames", "charred"),
    ("stole", "steal", "stolen", "pilfered", "robbed", "filched", "purloined"),
    ("poisoned", "poison", "laced", "contaminated", "envenomed", "dosed"),
    ("killed", "kill", "murdered", "assassinated", "slain", "slaughtered", "stabbed"),
    ("holds", "hold", "holding", "carrying", "possesses", "hid", "hiding", "concealed", "stashed"),
    ("forged", "forge", "fabricated", "counterfeited", "faked"),
    ("bribed", "bribe", "paid off", "corrupted"),
)

_PREDICATE_LOOKUP: dict[str, tuple[str, ...]] = {}
for _cluster in _PREDICATE_SYNONYM_CLUSTERS:
    for _word in _cluster:
        _PREDICATE_LOOKUP[_word] = _cluster


class EpistemicPromptFirewall:
    """Compiles character prompts strictly from their private EpistemicVault B_a(b, t)
    and verifies generated dialogue/actions against unlearned canonical secrets (including aliases & paraphrases).
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
        self._custom_aliases: dict[str, set[str]] = {}

    def register_aliases(self, canonical_token: str, *aliases: str) -> None:
        """Register human-readable aliases or paraphrases for an entity, item, or predicate."""
        key = canonical_token.strip().lower()
        if not key:
            return
        bucket = self._custom_aliases.setdefault(key, set())
        for al in aliases:
            cleaned = al.strip().lower()
            if cleaned:
                bucket.add(cleaned)

    def _candidate_surface_forms(self, token: str, *, is_predicate: bool = False) -> list[str]:
        """Return all surface strings (canonical ID, entity name/role, item name, predicate synonyms, custom aliases)."""
        raw = token.strip().lower()
        if not raw:
            return []
        forms: list[str] = [raw]

        if raw in self._custom_aliases:
            forms.extend(sorted(self._custom_aliases[raw]))

        if is_predicate:
            space_form = raw.replace("_", " ")
            if space_form != raw:
                forms.append(space_form)
            if raw in _PREDICATE_LOOKUP:
                forms.extend(_PREDICATE_LOOKUP[raw])
            elif space_form in _PREDICATE_LOOKUP:
                forms.extend(_PREDICATE_LOOKUP[space_form])
            return list(dict.fromkeys(forms))

        # Preserve strict exact matching for numbered benchmark identifiers (e.g., secret_artifact_0 vs secret_artifact_1)
        if raw[-1].isdigit():
            return list(dict.fromkeys(forms))

        if "_" in raw and len(raw) > 3:
            forms.append(raw.replace("_", " "))

        # Check AgentRegistry for character full name and role title
        ag = self.agents.get_agent(raw)
        if ag is not None:
            if ag.name:
                forms.append(ag.name.strip().lower())
            if ag.role and ag.role.lower() not in ("unknown", "npc", "agent"):
                role_low = ag.role.strip().lower()
                forms.append(role_low)
                forms.append(f"the {role_low}")

        # Check InventoryTracker for item display name and 2-word tail
        it = self.inventory.get_item(raw)
        if it is not None and it.name:
            it_name = it.name.strip().lower()
            forms.append(it_name)
            words = it_name.split()
            if len(words) >= 3:
                forms.append(" ".join(words[-2:]))

        return list(dict.fromkeys(f for f in forms if f))

    @staticmethod
    def _match_any_surface_form(lower_utt: str, candidates: list[str]) -> str | None:
        for cand in candidates:
            if cand and cand in lower_utt:
                return cand
        return None

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
        """Verify that `utterance` by `agent_id` does not reference canonical facts unknown to `agent_id`
        (either by canonical IDs or by character/item aliases and verb paraphrases).
        """
        agent_beliefs = self.vault.get_agent_beliefs(
            agent_id, branch_ref=branch_ref, query_tick=query_tick
        )
        all_visible_facts = self.vault.list_visible_facts(
            branch_ref=branch_ref, query_tick=query_tick
        )
        lower_utt = utterance.lower()
        leaks: list[dict[str, Any]] = []

        known_pred_obj_pairs = {
            (b.predicate.strip().lower(), b.obj.strip().lower())
            for b in agent_beliefs.values()
            if b.confidence > 0.0
        }

        for fact in all_visible_facts:
            if fact.fact_id in agent_beliefs and agent_beliefs[fact.fact_id].confidence > 0.0:
                continue

            subj_forms = self._candidate_surface_forms(fact.subject, is_predicate=False)
            pred_forms = self._candidate_surface_forms(fact.predicate, is_predicate=True)
            obj_forms = self._candidate_surface_forms(fact.obj, is_predicate=False)

            matched_subj = self._match_any_surface_form(lower_utt, subj_forms)
            matched_pred = self._match_any_surface_form(lower_utt, pred_forms)
            matched_obj = self._match_any_surface_form(lower_utt, obj_forms)

            shares_pred_obj_with_known = (
                fact.predicate.strip().lower(),
                fact.obj.strip().lower(),
            ) in known_pred_obj_pairs

            if shares_pred_obj_with_known:
                is_leaked = bool(matched_subj and matched_pred and matched_obj)
            else:
                is_leaked = bool(matched_pred and matched_obj)

            if is_leaked:
                leaks.append(
                    {
                        "agent_id": agent_id,
                        "leaked_fact_id": fact.fact_id,
                        "proposition": f"{fact.subject} {fact.predicate} {fact.obj}",
                        "origin_tick": fact.created_tick,
                        "matched_surface": {
                            "subject": matched_subj,
                            "predicate": matched_pred,
                            "object": matched_obj,
                        },
                    }
                )

        if leaks and raise_on_leak:
            first = leaks[0]
            raise EpistemicLeakTrap(
                f"EpistemicLeakTrap: Agent '{agent_id}' leaked unknown fact '{first['proposition']}' ({first['leaked_fact_id']})"
            )
        return leaks
