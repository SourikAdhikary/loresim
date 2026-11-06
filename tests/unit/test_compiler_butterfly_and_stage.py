"""Unit tests for the 7-Rule Continuity Compiler, Butterfly Blast Radius, Ingester, and StageDirector."""

from __future__ import annotations

from loresim.interfaces.engine import LoreSimEngine


def test_butterfly_blast_radius_and_stage_director(engine: LoreSimEngine) -> None:
    engine.seed_demo_mystery_world()

    # Disabling `ev_01_burn_treaty` breaks `ev_03_lie_clara`, `ev_04_rumor_thorne`, and `ev_05_lie_exposed`
    blast = engine.butterfly.compute_blast_radius("ev_01_burn_treaty")
    broken_ids = {b.broken_event_id for b in blast}
    assert "ev_03_lie_clara" in broken_ids
    assert "ev_04_rumor_thorne" in broken_ids
    assert "ev_05_lie_exposed" in broken_ids

    # StageDirector compiles 60 FPS StageFrame at Tick 2 (item transfer arc) and Tick 3 (crimson lie ring)
    frame2 = engine.get_stage_frame(tick=2)
    assert len(frame2.item_arcs) == 1
    assert frame2.item_arcs[0].item_id == "signet_dagger"

    frame3 = engine.get_stage_frame(tick=3)
    assert len(frame3.earshot_rings) == 1
    assert frame3.earshot_rings[0].ring_type == "LIE_CRIMSON"


def test_manuscript_ingester_dsl(engine: LoreSimEngine) -> None:
    script = """
    # Sample scene DSL
    @tick 1 | Day 1, 08:00 | Ch1 | study | vance | WITNESS_ACTION | target=kael | claim=vance:hid:gold_coin | text=Vance hid the gold coin.
    """
    parsed = engine.ingester.parse_script_lines(script)
    assert len(parsed) == 1
    assert parsed[0]["actor_id"] == "vance"
    assert parsed[0]["claims"][0]["object"] == "gold_coin"
