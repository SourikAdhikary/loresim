"""Example 01: Royal Treaty Murder/Conspiracy Stage Enactment & Live Detective Interrogation."""

from __future__ import annotations

import tempfile
from pathlib import Path

from loresim import LoreSimEngine


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        engine = LoreSimEngine(Path(tmp), world_name="RoyalTreatyMystery")
        engine.seed_demo_mystery_world()

        frame = engine.get_stage_frame(tick=3)
        print(f"=== 60 FPS StageFrame @ {frame.story_time} (Dramatic Irony: {frame.dramatic_irony_score}) ===")
        for p in frame.puppets:
            print(f"  - {p.name} ({p.location_id}) [{p.contagion_color}] expr={p.expression} | {p.god_mode_thought}")

        facts = [f.fact_id for f in engine.vault.list_visible_facts() if f.objective_truth]
        interrogation = engine.simulator.interrogate_suspect("vance", facts)
        print("\n=== Live Detective Interrogation ===")
        print(interrogation["statement"])
        engine.close()


if __name__ == "__main__":
    main()
