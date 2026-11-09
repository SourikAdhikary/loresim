"""Unit & integration tests for Phase 1 upgrades:
- G1: Multi-format ManuscriptIngester (Natural Prose, Fountain Screenplay, @tick DSL, & LLM JSON)
- G2: Pluggable LLMProvider + Self-Healing Epistemic Firewall Retry Loop in SceneSimulator
- G6: Entity/Item Alias Resolution & Verb Paraphrase Leak Detection in EpistemicPromptFirewall
"""

from __future__ import annotations

import json
from pathlib import Path

from loresim.core.llm import CallableLLMProvider
from loresim.interfaces.engine import LoreSimEngine


def test_g6_paraphrase_and_alias_leak_detection(tmp_path: Path) -> None:
    """Verify EpistemicPromptFirewall catches leaks via character roles, item names, verb synonyms, and custom aliases."""
    eng = LoreSimEngine(tmp_path / "g6_ws")
    try:
        eng.seed_demo_mystery_world()
        eng.firewall.register_aliases("royal_treaty", "the king's parchment", "sacred accord")

        # Clara at tick 3 believes 'northern_rebels stole royal_treaty' and does NOT know 'vance burned royal_treaty'
        # 1. Paraphrase using role ("the Chancellor"), verb synonym ("incinerated"), and item name ("Peace Treaty")
        leaks_paraphrase = eng.firewall.audit_utterance_for_leaks(
            agent_id="clara",
            utterance="I suspect the Chancellor incinerated the Peace Treaty in the hearth!",
            query_tick=3,
            raise_on_leak=False,
        )
        assert len(leaks_paraphrase) == 1
        assert leaks_paraphrase[0]["proposition"] == "vance burned royal_treaty"
        assert leaks_paraphrase[0]["matched_surface"]["predicate"] == "incinerated"
        assert leaks_paraphrase[0]["matched_surface"]["object"] == "peace treaty"

        # 2. Paraphrase using custom alias ("the king's parchment") + synonym ("torched")
        leaks_custom = eng.firewall.audit_utterance_for_leaks(
            agent_id="clara",
            utterance="Someone torched the king's parchment last night!",
            query_tick=3,
            raise_on_leak=False,
        )
        assert len(leaks_custom) == 1
        assert leaks_custom[0]["proposition"] == "vance burned royal_treaty"

        # 3. Saying what Clara actually believes ("Northern Rebels stole the Royal Peace Treaty") has 0 leaks
        leaks_allowed = eng.firewall.audit_utterance_for_leaks(
            agent_id="clara",
            utterance="Northern Rebels stole the Royal Peace Treaty from the study!",
            query_tick=3,
            raise_on_leak=False,
        )
        assert len(leaks_allowed) == 0
    finally:
        eng.close()


def test_g2_llm_provider_self_healing_firewall_retry_and_redaction(tmp_path: Path) -> None:
    """Verify SceneSimulator retries leaking LLM drafts and redacts persistent leaks."""
    eng = LoreSimEngine(tmp_path / "g2_ws")
    try:
        eng.seed_demo_mystery_world()

        # Case 1: LLM leaks on attempt 1, then self-corrects on attempt 2 after firewall rejection prompt
        prompts_seen: list[str] = []

        def healing_llm(sys_prompt: str, user_prompt: str) -> str:
            _ = sys_prompt
            prompts_seen.append(user_prompt)
            if "EPISTEMIC FIREWALL REJECTION" not in user_prompt:
                # Attempt 1: tries to leak unknown secret using paraphrase!
                return "Lord Vance incinerated the Royal Peace Treaty in the study!"
            # Attempt 2: obeys rejection instruction and states only believed rumor
            return "Tragic news—Northern Rebels stole the Royal Peace Treaty."

        provider = CallableLLMProvider(healing_llm, name="mock-healing-llm")
        res = eng.simulator.generate_sandboxed_response(
            agent_id="clara",
            topic_query="royal_treaty",
            query_tick=3,
            llm_provider=provider,
        )
        assert res["llm_provider"] == "mock-healing-llm"
        assert res["firewall_retries"] == 1
        assert res["firewall_redacted"] is False
        assert res["leaks_detected"] == 0
        assert "Northern Rebels stole the Royal Peace Treaty" in res["utterance"]
        assert len(prompts_seen) == 2

        # Case 2: Adversarial LLM keeps leaking on every retry -> Firewall redacts to safe deterministic fallback
        adv_provider = CallableLLMProvider(
            lambda s, u: "Vance burned the Royal Peace Treaty!",
            name="mock-adversarial-llm",
        )
        res_redacted = eng.simulator.generate_sandboxed_response(
            agent_id="clara",
            topic_query="royal_treaty",
            query_tick=3,
            llm_provider=adv_provider,
        )
        assert res_redacted["firewall_redacted"] is True
        assert res_redacted["leaks_detected"] == 0
        assert "burned" not in res_redacted["utterance"].lower()
    finally:
        eng.close()


def test_g1_natural_prose_fountain_and_llm_manuscript_ingestion(tmp_path: Path) -> None:
    """Verify ManuscriptIngester parses natural Markdown prose, Fountain screenplay blocks, and LLM JSON."""
    eng = LoreSimEngine(tmp_path / "g1_ws")
    try:
        eng.spatial.add_location("study", "Royal Study", "Citadel", x_coord=190.0, y_coord=160.0)
        eng.spatial.add_location("great_hall", "Great Banquet Hall", "Citadel", x_coord=540.0, y_coord=160.0)
        eng.spatial.add_location("courtyard", "Citadel Courtyard", "Citadel", x_coord=190.0, y_coord=410.0)
        eng.spatial.add_route("study", "great_hall", travel_minutes=5)
        eng.spatial.add_route("great_hall", "courtyard", travel_minutes=10)

        eng.agents.register_agent("vance", "Lord Vance", role="Chancellor", initial_location_id="study", tick=0)
        eng.agents.register_agent("kael", "Captain Kael", role="Royal Guard", initial_location_id="study", tick=0)
        eng.agents.register_agent("mira", "Spymaster Mira", role="Whisper Broker", initial_location_id="great_hall", tick=0)
        eng.agents.register_agent("clara", "Lady Clara", role="Ambassador", initial_location_id="great_hall", tick=0)
        eng.agents.register_agent("thorne", "General Thorne", role="Warlord", initial_location_id="courtyard", tick=0)

        eng.inventory.register_item("royal_treaty", "Royal Peace Treaty", is_unique=True, initial_holder_id="vance", tick=0)
        eng.inventory.register_item("signet_dagger", "Valen Signet Dagger", is_unique=True, initial_holder_id="vance", tick=0)

        manuscript = """
        # The Royal Treaty Conspiracy

        ## Chapter 1: Royal Study (Day 1, 09:00)
        Lord Vance secretly burned the Royal Peace Treaty while Captain Kael watched.

        INT. GREAT BANQUET HALL - DAY 1, 09:15
        Lord Vance walked to the Great Banquet Hall.
        Lord Vance slipped the Valen Signet Dagger to Spymaster Mira.

        VANCE
        (lying to Lady Clara)
        Northern Rebels stole the Royal Peace Treaty!

        ## Chapter 2: Citadel Courtyard (Day 1, 09:45)
        Lady Clara told General Thorne that Northern Rebels stole the Royal Peace Treaty.
        Lady Clara used the Valen Signet Dagger.
        """

        ingest_result = eng.ingest_manuscript(manuscript)
        assert ingest_result["events_count"] == 6
        event_types = [e["event_type"] for e in ingest_result["events"]]
        assert event_types == ["WITNESS_ACTION", "MOVE", "GIVE_ITEM", "LIE", "TELL", "USE_ITEM"]

        # Verify LINT-03 caught Clara using the Valen Signet Dagger while Mira holds it!
        rule_codes = [v["rule_code"] for v in ingest_result["violations"]]
        assert "LINT-03" in rule_codes

        # Verify LLM-assisted JSON extraction mode
        mock_llm = CallableLLMProvider(
            lambda s, u: json.dumps(
                {
                    "events": [
                        {
                            "tick": 10,
                            "story_time_minutes": 300,
                            "chapter_ref": "Ch3",
                            "location_id": "study",
                            "actor_id": "kael",
                            "event_type": "TELL",
                            "target_ids": ["clara"],
                            "visibility": "PUBLIC_HERE",
                            "item_id": None,
                            "claims": [{"subject": "vance", "predicate": "burned", "object": "royal_treaty", "is_secret": False}],
                            "summary": "Kael reveals Vance burned the treaty",
                            "raw_text": "I saw Vance burn the treaty!",
                        }
                    ]
                }
            ),
            name="mock-json-ingester",
        )
        llm_parsed = eng.ingester.parse_script_lines("Freeform literary paragraph.", use_llm=True, llm_provider=mock_llm)
        assert len(llm_parsed) == 1
        assert llm_parsed[0]["actor_id"] == "kael"
    finally:
        eng.close()
