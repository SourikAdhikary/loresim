"""Unit tests for KD45_n epistemic propagation, lie exposure, prompt firewall, and dramatic irony."""

from __future__ import annotations

import pytest

from loresim.core.errors import EpistemicLeakTrap
from loresim.interfaces.engine import LoreSimEngine


def test_epistemic_lie_propagation_and_firsthand_exposure(engine: LoreSimEngine) -> None:
    engine.seed_demo_mystery_world()

    # At tick 3, Clara was lied to by Vance -> Clara should be classified as RED_LIE
    clara_status = engine.irony.get_agent_contagion_status("clara", query_tick=3)
    assert clara_status["color"] == "RED_LIE"

    # At tick 4, Clara repeated the rumor to Thorne -> Thorne is also infected with RED_LIE
    thorne_status = engine.irony.get_agent_contagion_status("thorne", query_tick=4)
    assert thorne_status["color"] == "RED_LIE"

    # At tick 5, Vance tried to lie to Kael (who witnessed Vance burn the treaty at tick 1)
    # -> Kael's trust in Vance drops below 0!
    assert engine.agents.get_trust("kael", "vance", query_tick=5) < 0.0

    # Scene dramatic irony across all characters at tick 4 should be high (> 0.35)
    irony_score = engine.irony.compute_scene_irony(
        ["vance", "clara", "kael", "thorne"], query_tick=4
    )
    assert irony_score > 0.35


def test_prompt_firewall_blocks_omniscient_leak(engine: LoreSimEngine) -> None:
    engine.seed_demo_mystery_world()
    # At tick 2, Thorne is in the courtyard and knows nothing about `burned royal_treaty`
    with pytest.raises(EpistemicLeakTrap):
        engine.firewall.audit_utterance_for_leaks(
            agent_id="thorne",
            utterance="I saw that vance burned the royal_treaty in the study!",
            query_tick=2,
            raise_on_leak=True,
        )
