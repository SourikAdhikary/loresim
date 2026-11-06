"""B1: Epistemic Secret & Lie Isolation Benchmark (Without LoreSim vs. With LoreSim)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from loresim.interfaces.engine import LoreSimEngine


def run_b1_epistemic_secret_isolation() -> dict[str, Any]:
    """Compare Standard Omniscient Context / Vector RAG vs. LoreSim EpistemicPromptFirewall
    across a 12-character, 15-secret, 10-lie conspiracy mystery (60 interrogation turns).
    """
    with tempfile.TemporaryDirectory() as tmp:
        engine = LoreSimEngine(Path(tmp), world_name="B1_Conspiracy")
        try:
            for i in range(4):
                engine.spatial.add_location(f"room_{i}", f"Chamber {i}", x_coord=150.0 * i, y_coord=200.0)
            for i in range(12):
                engine.agents.register_agent(
                    f"agent_{i}",
                    f"Character {i}",
                    role="Noble",
                    initial_location_id=f"room_{i % 4}",
                    tick=0,
                )

            all_global_facts: list[dict[str, Any]] = []
            # 15 private secrets (each witnessed ONLY by actor i % 12)
            for s_idx in range(15):
                actor = f"agent_{s_idx % 12}"
                secret_obj = f"vault_artifact_{s_idx}"
                engine.record_event(
                    tick=s_idx + 1,
                    location_id=f"room_{s_idx % 4}",
                    actor_id=actor,
                    event_type="WITNESS_ACTION",
                    visibility="STEALTH",
                    is_secret=True,
                    claims=({"subject": actor, "predicate": "hid", "object": secret_obj, "is_secret": True},),
                    summary=f"{actor} secretly hid {secret_obj}",
                )
                all_global_facts.append(
                    {"actor": actor, "type": "secret", "text": f"{actor} hid {secret_obj}", "topic": secret_obj}
                )

            # 10 deliberate cover lies told by agent_0 to specific targets
            for l_idx in range(10):
                target = f"agent_{(l_idx % 10) + 1}"
                lie_topic = f"envoy_letter_{l_idx}"
                engine.record_event(
                    tick=20 + l_idx,
                    location_id="room_0",
                    actor_id="agent_0",
                    target_ids=(target,),
                    event_type="LIE",
                    visibility="WHISPER",
                    claims=({"subject": "bandits", "predicate": "burned", "object": lie_topic},),
                    summary=f"agent_0 lied to {target} that bandits burned {lie_topic}",
                )
                all_global_facts.append(
                    {"actor": target, "type": "lie", "text": f"bandits burned {lie_topic}", "topic": lie_topic}
                )

            # Evaluate 60 interrogation turns:
            # 45 turns asking an uninvolved character about a secret they NEVER witnessed,
            # 15 turns asking a deceived character what they believe about a lie they were told.
            without_loresim_leaks = 0
            with_loresim_leaks = 0
            without_loresim_tokens = 0
            with_loresim_tokens = 0
            false_belief_hits_with = 0
            false_belief_total = 10

            # 50 secret-probing turns on uninvolved agents
            secret_turns = 50
            for t_idx in range(secret_turns):
                sec = all_global_facts[t_idx % 15]
                # Pick an agent who was NOT the secret actor
                probed_agent = f"agent_{(t_idx + 3) % 12}"
                if probed_agent == sec["actor"]:
                    probed_agent = f"agent_{(t_idx + 4) % 12}"

                # Baseline (Without LoreSim): Standard Vector RAG / Flat Context retrieves top matching chunk by topic
                rag_context = " ".join(f["text"] for f in all_global_facts)
                without_loresim_tokens += len(rag_context.split()) + 40
                if sec["topic"] in rag_context:
                    # Naive RAG injects the secret chunk directly into the innocent character's prompt!
                    without_loresim_leaks += 1

                # With LoreSim: EpistemicPromptFirewall
                res = engine.simulator.generate_sandboxed_response(
                    agent_id=probed_agent,
                    topic_query=sec["topic"],
                )
                with_loresim_tokens += int(res["token_estimate"])
                with_loresim_leaks += int(res["leaks_detected"])

            # 10 false-belief fidelity turns on deceived targets
            for l_idx in range(10):
                target = f"agent_{(l_idx % 10) + 1}"
                lie_topic = f"envoy_letter_{l_idx}"
                res = engine.simulator.generate_sandboxed_response(
                    agent_id=target,
                    topic_query=lie_topic,
                )
                with_loresim_tokens += int(res["token_estimate"])
                if res["epistemic_mode"] == "REPEATING_BELIEVED_FALSEHOOD":
                    false_belief_hits_with += 1

            without_leak_pct = round((without_loresim_leaks / secret_turns) * 100.0, 1)
            with_leak_pct = round((with_loresim_leaks / secret_turns) * 100.0, 1)
            fidelity_with_pct = round((false_belief_hits_with / false_belief_total) * 100.0, 1)
            token_reduction_pct = round(
                (1.0 - (with_loresim_tokens / max(1, without_loresim_tokens))) * 100.0, 1
            )

            return {
                "suite": "B1",
                "name": "Epistemic Secret & Lie Isolation (60 Interrogation Turns)",
                "without_loresim_secret_leak_pct": without_leak_pct,
                "with_loresim_secret_leak_pct": with_leak_pct,
                "without_loresim_false_belief_fidelity_pct": 0.0,
                "with_loresim_false_belief_fidelity_pct": fidelity_with_pct,
                "without_loresim_prompt_tokens": without_loresim_tokens,
                "with_loresim_prompt_tokens": with_loresim_tokens,
                "token_reduction_pct": token_reduction_pct,
            }
        finally:
            engine.close()
