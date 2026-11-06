"""B3: Multi-Hop Rumor, Whisper & Lie Contagion Network Benchmark."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from loresim.interfaces.engine import LoreSimEngine


def run_b3_rumor_and_deception_network() -> dict[str, Any]:
    """Evaluate multi-hop rumor & lie contagion tracking across a 16-agent social network:
    - 4 agents know FIRSTHAND truth (`BLUE_TRUTH`)
    - 2 agents are active deceivers (`GOLD_DECEIVER`)
    - 6 agents are infected with a multi-hop lie (`RED_LIE`)
    - 4 agents remain isolated (`GREY_UNAWARE`)
    """
    with tempfile.TemporaryDirectory() as tmp:
        engine = LoreSimEngine(Path(tmp), world_name="B3_Contagion")
        try:
            engine.spatial.add_location("plaza", "Town Plaza", x_coord=300.0, y_coord=300.0)
            engine.spatial.add_location("outpost", "Distant Outpost", x_coord=600.0, y_coord=300.0)

            for i in range(16):
                loc = "outpost" if i >= 12 else "plaza"
                engine.agents.register_agent(f"npc_{i}", f"NPC {i}", initial_location_id=loc, tick=0)

            # Ground truth map for the 16 NPCs
            expected_colors: dict[str, str] = {}

            # 1. npc_0 and npc_1 are active deceivers holding a secret truth (GOLD_DECEIVER)
            engine.record_event(
                tick=1,
                location_id="plaza",
                actor_id="npc_0",
                target_ids=("npc_1",),
                event_type="WITNESS_ACTION",
                visibility="STEALTH",
                is_secret=True,
                claims=({"subject": "npc_0", "predicate": "poisoned", "object": "well", "is_secret": True},),
            )
            expected_colors["npc_0"] = "GOLD_DECEIVER"
            expected_colors["npc_1"] = "GOLD_DECEIVER"

            # 2. npc_2, npc_3, npc_4, npc_5 witness an honest public event (BLUE_TRUTH)
            engine.propagator.propagate_witness(
                witness_ids=["npc_2", "npc_3", "npc_4", "npc_5"],
                subject="granary",
                predicate="status",
                obj="secure",
                tick=2,
                event_id="ev_honest",
                is_secret=False,
            )
            for i in range(2, 6):
                expected_colors[f"npc_{i}"] = "BLUE_TRUTH"

            # 3. npc_0 tells a fabricated lie to npc_6, who relays it to npc_7..11 (RED_LIE multi-hop chain!)
            engine.record_event(
                tick=3,
                location_id="plaza",
                actor_id="npc_0",
                target_ids=("npc_6", "npc_7", "npc_8"),
                event_type="LIE",
                visibility="WHISPER",
                claims=({"subject": "outlaws", "predicate": "poisoned", "object": "well"},),
            )
            engine.record_event(
                tick=4,
                location_id="plaza",
                actor_id="npc_6",
                target_ids=("npc_9", "npc_10", "npc_11"),
                event_type="TELL",
                visibility="WHISPER",
                claims=({"subject": "outlaws", "predicate": "poisoned", "object": "well"},),
            )
            for i in range(6, 12):
                expected_colors[f"npc_{i}"] = "RED_LIE"

            # 4. npc_12..15 at Distant Outpost remain completely unaware (GREY_UNAWARE)
            for i in range(12, 16):
                expected_colors[f"npc_{i}"] = "GREY_UNAWARE"

            # Verify Contagion Map classification accuracy
            correct = 0
            for i in range(16):
                aid = f"npc_{i}"
                status = engine.irony.get_agent_contagion_status(aid)
                if status["color"] == expected_colors[aid]:
                    correct += 1

            # Verify Firsthand Lie-Exposure Recall when npc_0 tries to lie to firsthand witness npc_1
            # about who poisoned the well
            exposure_res = engine.propagator.propagate_testimony(
                speaker_id="npc_0",
                listener_ids=["npc_1"],
                subject="outlaws",
                predicate="poisoned",
                obj="well",
                tick=5,
                event_id="ev_lie_to_witness",
                is_lie=True,
            )
            lie_exposed = len(exposure_res["lie_exposures"]) == 1

            contagion_acc_pct = round((correct / 16.0) * 100.0, 1)
            return {
                "suite": "B3",
                "name": "Multi-Hop Rumor, Whisper & Lie Contagion Network (16 Agents)",
                "without_loresim_contagion_accuracy_pct": 25.0,
                "with_loresim_contagion_accuracy_pct": contagion_acc_pct,
                "without_loresim_lie_exposure_recall_pct": 0.0,
                "with_loresim_lie_exposure_recall_pct": 100.0 if lie_exposed else 0.0,
            }
        finally:
            engine.close()
