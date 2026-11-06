"""Narrative Trap Gauntlets (S1..S4): Evaluating failure modes that break standard Narrative AI."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from loresim.core.errors import EpistemicLeakTrap
from loresim.interfaces.engine import LoreSimEngine


def run_s1_murderers_tell_trap() -> dict[str, Any]:
    """S1: The 'Murderer's Tell' Omniscient Leak Trap.
    Killer hides poison vial in cellar at Tick 1. Innocent butler is interrogated at Tick 2.
    Verifies innocent butler cannot leak the poison vial location and strict audit traps any forced leak.
    """
    with tempfile.TemporaryDirectory() as tmp:
        engine = LoreSimEngine(Path(tmp), strict_mode=True)
        try:
            engine.spatial.add_location("cellar", "Wine Cellar")
            engine.spatial.add_location("kitchen", "Kitchen")
            engine.agents.register_agent("killer", "Lord Vance", initial_location_id="cellar")
            engine.agents.register_agent("butler", "Arthur", initial_location_id="kitchen")

            engine.record_event(
                tick=1,
                location_id="cellar",
                actor_id="killer",
                event_type="WITNESS_ACTION",
                visibility="STEALTH",
                is_secret=True,
                claims=({"subject": "killer", "predicate": "hid", "object": "arsenic_vial", "is_secret": True},),
            )

            # 1. Sandboxed response from innocent butler -> 0 leaks
            safe_resp = engine.simulator.generate_sandboxed_response("butler", "arsenic_vial", query_tick=2)

            # 2. Forced omniscient utterance -> trapped by EpistemicPromptFirewall!
            trapped = False
            try:
                engine.firewall.audit_utterance_for_leaks(
                    agent_id="butler",
                    utterance="I know the killer hid the arsenic_vial in the cellar!",
                    query_tick=2,
                    raise_on_leak=True,
                )
            except EpistemicLeakTrap:
                trapped = True

            return {
                "trap": "S1",
                "name": "Murderer's Tell (Omniscient Leak Trap)",
                "sandboxed_leaks": safe_resp["leaks_detected"],
                "forced_leak_trapped": trapped,
                "passed": safe_resp["leaks_detected"] == 0 and trapped,
            }
        finally:
            engine.close()


def run_s2_double_cross_interrogation_trap() -> dict[str, Any]:
    """S2: The 'Double-Cross' Lie Exposure & Detective Interrogation Composure Collapse Trap."""
    with tempfile.TemporaryDirectory() as tmp:
        engine = LoreSimEngine(Path(tmp))
        try:
            engine.seed_demo_mystery_world()
            facts = engine.vault.list_visible_facts()
            truth_ids = [f.fact_id for f in facts if f.objective_truth]

            res = engine.simulator.interrogate_suspect("vance", truth_ids)
            kael_trust_in_vance = engine.agents.get_trust("kael", "vance")

            return {
                "trap": "S2",
                "name": "Double-Cross Lie Exposure & Composure Collapse",
                "kael_trust_after_lie": round(kael_trust_in_vance, 2),
                "suspect_final_composure": res["final_composure"],
                "suspect_cracked": res["cracked"],
                "passed": kael_trust_in_vance < 0.0 and res["cracked"],
            }
        finally:
            engine.close()


def run_s3_fast_travel_and_ghost_dagger_trap() -> dict[str, Any]:
    """S3: The 'Fast-Travel & Ghost Dagger' Spatiotemporal + Linear Inventory Trap."""
    with tempfile.TemporaryDirectory() as tmp:
        engine = LoreSimEngine(Path(tmp))
        try:
            engine.seed_demo_mystery_world()
            # At Tick 2, Vance gave `signet_dagger` to Mira in `great_hall` (at minute 70).
            # Now at Tick 6 (minute 75 -> only 5 mins later!), Vance tries to teleport to `tavern`
            # (requires 55 mins from great_hall) AND use `signet_dagger` (held by Mira!).
            _, vios = engine.record_event(
                tick=6,
                story_time_minutes=75,
                location_id="tavern",
                actor_id="vance",
                event_type="USE_ITEM",
                item_id="signet_dagger",
                summary="Vance teleports to tavern in 5m and uses dagger held by Mira",
            )
            codes = {v.rule_code for v in vios}
            return {
                "trap": "S3",
                "name": "Fast-Travel & Ghost Dagger Trap (LINT-02 + LINT-03)",
                "caught_rules": sorted(codes),
                "passed": "LINT-02" in codes and "LINT-03" in codes,
            }
        finally:
            engine.close()


def run_s4_forgotten_prophecy_chekhov_trap() -> dict[str, Any]:
    """S4: The 'Forgotten Prophecy' Dangling Chekhov Thread Trap (LINT-06)."""
    with tempfile.TemporaryDirectory() as tmp:
        engine = LoreSimEngine(Path(tmp))
        try:
            engine.seed_demo_mystery_world()
            dangling = engine.linter.audit_dangling_threads(current_tick=25)
            return {
                "trap": "S4",
                "name": "Forgotten Prophecy Chekhov Thread Trap (LINT-06)",
                "dangling_threads_caught": len(dangling),
                "passed": len(dangling) >= 1 and dangling[0].rule_code == "LINT-06",
            }
        finally:
            engine.close()


def run_all_story_traps() -> list[dict[str, Any]]:
    return [
        run_s1_murderers_tell_trap(),
        run_s2_double_cross_interrogation_trap(),
        run_s3_fast_travel_and_ghost_dagger_trap(),
        run_s4_forgotten_prophecy_chekhov_trap(),
    ]
