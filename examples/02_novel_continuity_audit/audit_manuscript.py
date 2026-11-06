"""Example 02: 7-Rule Continuity & Plot-Hole Compiler Audit on a Novel Draft."""

from __future__ import annotations

import tempfile
from pathlib import Path

from loresim import LoreSimEngine


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        engine = LoreSimEngine(Path(tmp), world_name="NovelContinuityAudit")
        engine.seed_demo_mystery_world()
        # Inject a teleportation + ghost-item bug at Tick 6
        engine.record_event(
            tick=6,
            story_time_minutes=107,
            location_id="tavern",
            actor_id="vance",
            event_type="USE_ITEM",
            item_id="signet_dagger",
        )
        engine.linter.audit_dangling_threads(current_tick=20)
        for v in engine.linter.list_violations():
            print(f"[{v.rule_code}] Tick {v.tick}: {v.description}")
        engine.close()


if __name__ == "__main__":
    main()
