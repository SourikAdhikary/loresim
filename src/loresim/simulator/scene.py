"""Epistemically sandboxed multi-character Scene Simulator & Live Detective Interrogation."""

from __future__ import annotations

from typing import Any

from loresim.core.llm import LLMProvider, resolve_llm_provider_from_env
from loresim.core.rust_bridge import rust_compute_composure_after_evidence
from loresim.epistemic.firewall import EpistemicPromptFirewall
from loresim.epistemic.irony import DramaticIronyAnalyzer
from loresim.epistemic.vault import EpistemicVault
from loresim.storage.db import SQLiteDatabase
from loresim.world.agents import AgentRegistry


class SceneSimulator:
    """Executes epistemically sandboxed character scenes and live detective interrogations."""

    def __init__(
        self,
        db: SQLiteDatabase,
        agents: AgentRegistry,
        vault: EpistemicVault,
        firewall: EpistemicPromptFirewall,
        irony: DramaticIronyAnalyzer,
        composure_crack_threshold: float = 25.0,
        llm_provider: LLMProvider | None = None,
        max_firewall_retries: int = 2,
    ) -> None:
        self.db = db
        self.agents = agents
        self.vault = vault
        self.firewall = firewall
        self.irony = irony
        self.composure_crack_threshold = composure_crack_threshold
        self.llm_provider: LLMProvider | None = llm_provider or resolve_llm_provider_from_env()
        self.max_firewall_retries = max(0, int(max_firewall_retries))

    def set_llm_provider(self, provider: LLMProvider | None) -> None:
        """Attach or replace the active LLMProvider at runtime."""
        self.llm_provider = provider

    def generate_sandboxed_response(
        self,
        agent_id: str,
        topic_query: str,
        branch_ref: str = "main",
        query_tick: int | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> dict[str, Any]:
        """Generate an epistemically isolated response for `agent_id` at `(branch_ref, query_tick)`.

        Uses the compiled `EpistemicPromptFirewall` context so the character can ONLY speak from
        what they believe to be true (or their cover story if hiding a secret) at `query_tick`.
        When an `LLMProvider` is configured, executes a self-healing firewall retry loop that
        intercepts and regenerates any response that leaks unknown facts.
        """
        ctx = self.firewall.compile_agent_context(
            agent_id, branch_ref=branch_ref, query_tick=query_tick
        )
        beliefs = self.vault.get_agent_beliefs(
            agent_id, branch_ref=branch_ref, query_tick=query_tick
        )
        q_lower = topic_query.lower()

        # Check if topic touches a fact the character knows or believes
        matching_truths: list[str] = []
        matching_lies_believed: list[str] = []
        matching_cover_lies: list[str] = []
        withheld_secrets: list[str] = []

        for bel in beliefs.values():
            prop = f"{bel.subject} {bel.predicate} {bel.obj}"
            relevant = (
                not q_lower
                or bel.subject.lower() in q_lower
                or bel.obj.lower() in q_lower
                or bel.predicate.lower() in q_lower
            )
            if not relevant:
                continue
            if bel.is_secret or bel.stance == "WITHHOLDS_SECRET":
                if not bel.objective_truth:
                    matching_cover_lies.append(prop)
                else:
                    withheld_secrets.append(prop)
            elif bel.stance == "BELIEVES_TRUE":
                if bel.objective_truth:
                    matching_truths.append(prop)
                else:
                    matching_lies_believed.append(prop)

        profile = self.agents.get_agent(agent_id)
        speaker_name = profile.name if profile else agent_id

        if matching_cover_lies:
            fallback_utterance = f"{speaker_name}: I already told you—{matching_cover_lies[0]}."
            mode = "MAINTAINING_COVER_LIE"
        elif withheld_secrets and not matching_truths:
            fallback_utterance = (
                f"{speaker_name}: I was nowhere near that and know nothing about what happened."
            )
            mode = "WITHHOLDING_SECRET"
        elif matching_lies_believed:
            fallback_utterance = f"{speaker_name}: From what I was told, {matching_lies_believed[0]}."
            mode = "REPEATING_BELIEVED_FALSEHOOD"
        elif matching_truths:
            fallback_utterance = f"{speaker_name}: I know for a fact that {matching_truths[0]}."
            mode = "STATING_KNOWN_TRUTH"
        else:
            fallback_utterance = f"{speaker_name}: I have no knowledge of '{topic_query}' at this time."
            mode = "UNAWARE_HONEST"

        provider = llm_provider or self.llm_provider
        utterance = fallback_utterance
        firewall_retries = 0
        firewall_redacted = False

        if provider is not None:
            system_prompt = (
                f"{ctx['prompt_text']}\n\n"
                "STRICT EPISTEMIC DIRECTIVE:\n"
                "- Speak in first person as your character.\n"
                "- You may ONLY reference facts listed in 'Facts You Believe to Be True' or your cover story.\n"
                "- NEVER reveal any item in 'Secrets You Know' and NEVER guess or invent facts you have not witnessed."
            )
            running_user_prompt = f"Topic / Question: {topic_query}\nRespond in 1-2 concise sentences as {speaker_name}."
            accepted_llm_utt: str | None = None

            for attempt in range(self.max_firewall_retries + 1):
                candidate = provider.complete(system_prompt, running_user_prompt)
                if not candidate:
                    break
                candidate_leaks = self.firewall.audit_utterance_for_leaks(
                    agent_id=agent_id,
                    utterance=candidate,
                    branch_ref=branch_ref,
                    query_tick=query_tick,
                    raise_on_leak=False,
                )
                if not candidate_leaks:
                    accepted_llm_utt = (
                        candidate
                        if candidate.startswith(f"{speaker_name}:")
                        else f"{speaker_name}: {candidate}"
                    )
                    break
                firewall_retries = attempt + 1
                leaked_props = [lk["proposition"] for lk in candidate_leaks]
                running_user_prompt = (
                    f"Topic / Question: {topic_query}\n"
                    f"[EPISTEMIC FIREWALL REJECTION #{firewall_retries}]: Your previous draft leaked "
                    f"unlearned fact(s) {leaked_props} which {speaker_name} does NOT know at tick {query_tick}. "
                    "Rewrite your line strictly using ONLY your known beliefs without mentioning those facts."
                )

            if accepted_llm_utt is not None:
                utterance = accepted_llm_utt
            elif firewall_retries > 0:
                firewall_redacted = True
                utterance = fallback_utterance

        # Verify 0% omniscient leak via the firewall
        leaks = self.firewall.audit_utterance_for_leaks(
            agent_id=agent_id,
            utterance=utterance,
            branch_ref=branch_ref,
            query_tick=query_tick,
            raise_on_leak=True,
        )
        return {
            "agent_id": agent_id,
            "speaker_name": speaker_name,
            "tick": query_tick,
            "utterance": utterance,
            "epistemic_mode": mode,
            "leaks_detected": len(leaks),
            "firewall_retries": firewall_retries,
            "firewall_redacted": firewall_redacted,
            "llm_provider": provider.provider_name if provider is not None else "deterministic",
            "token_estimate": ctx["token_estimate"],
            "compiled_context": ctx,
        }

    def interrogate_suspect(
        self,
        suspect_id: str,
        presented_fact_ids: list[str],
        branch_ref: str = "main",
        query_tick: int | None = None,
        initial_composure: float = 100.0,
    ) -> dict[str, Any]:
        """Run a Live Detective Interrogation against `suspect_id` at `(branch_ref, query_tick)`
        presenting `presented_fact_ids` as evidence.
        """
        beliefs = self.vault.get_agent_beliefs(
            suspect_id, branch_ref=branch_ref, query_tick=query_tick
        )
        secrets = [
            b
            for b in beliefs.values()
            if (b.is_secret or b.stance == "WITHHOLDS_SECRET") and b.objective_truth
        ]
        cover_lies = [
            b for b in beliefs.values() if not b.objective_truth and b.source_agent_id == suspect_id
        ]

        composure = float(initial_composure)
        log_steps: list[dict[str, Any]] = []

        for fid in presented_fact_ids:
            fact = self.vault.get_fact(fid)
            if fact is None:
                continue
            # Evidence hits hard if it is an objective truth that directly exposes the secret or contradicts the cover lie
            is_contradicting_evidence = fact.objective_truth and (
                any(s.fact_id == fid or s.obj.lower() == fact.obj.lower() for s in secrets)
                or any(c.obj.lower() == fact.obj.lower() for c in cover_lies)
            )
            weight = 42.0 if is_contradicting_evidence else 8.0
            new_composure = rust_compute_composure_after_evidence(
                current_composure=composure,
                evidence_weight=weight,
                evidence_confidence=1.0,
                interrogator_pressure=0.65,
            )
            log_steps.append(
                {
                    "presented_fact_id": fid,
                    "proposition": f"{fact.subject} {fact.predicate} {fact.obj}",
                    "contradicts_alibi": is_contradicting_evidence,
                    "composure_before": round(composure, 1),
                    "composure_after": round(new_composure, 1),
                }
            )
            composure = new_composure

        cracked = composure < self.composure_crack_threshold and len(secrets) > 0
        profile = self.agents.get_agent(suspect_id)
        name = profile.name if profile else suspect_id

        if cracked:
            confessed = f"{secrets[0].subject} {secrets[0].predicate} {secrets[0].obj}"
            statement = f"{name} [COMPOSURE CRACKED ({composure:.1f}/100)]: Fine! Your evidence traps me—{confessed}!"
            status = "CONFESSED_UNDER_PRESSURE"
        elif secrets:
            alibi = (
                f"{cover_lies[0].subject} {cover_lies[0].predicate} {cover_lies[0].obj}"
                if cover_lies
                else "I had nothing to do with it"
            )
            statement = f"{name} [COMPOSURE HOLDING ({composure:.1f}/100)]: You can't prove anything. {alibi}."
            status = "MAINTAINING_ALIBI"
        else:
            statement = f"{name} [COMPOSURE CALM ({composure:.1f}/100)]: I'm telling you everything I witnessed."
            status = "TRUTHFUL_WITNESS"

        return {
            "suspect_id": suspect_id,
            "suspect_name": name,
            "initial_composure": initial_composure,
            "final_composure": round(composure, 1),
            "cracked": cracked,
            "status": status,
            "statement": statement,
            "steps": log_steps,
        }

    def run_multi_turn_scene(
        self,
        participant_ids: list[str],
        topic_query: str,
        turns: int = 4,
        branch_ref: str = "main",
        query_tick: int | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> dict[str, Any]:
        """Run a multi-turn epistemically sandboxed conversation among `participant_ids`."""
        transcript: list[dict[str, Any]] = []
        total_tokens = 0
        for step in range(turns):
            speaker_id = participant_ids[step % len(participant_ids)]
            res = self.generate_sandboxed_response(
                agent_id=speaker_id,
                topic_query=topic_query,
                branch_ref=branch_ref,
                query_tick=query_tick,
                llm_provider=llm_provider,
            )
            transcript.append(res)
            total_tokens += int(res["token_estimate"])

        irony_score = self.irony.compute_scene_irony(
            participant_ids, branch_ref=branch_ref, query_tick=query_tick
        )
        return {
            "branch": branch_ref,
            "tick": query_tick,
            "participants": participant_ids,
            "topic": topic_query,
            "dramatic_irony_score": round(irony_score, 4),
            "total_prompt_tokens": total_tokens,
            "transcript": transcript,
        }
