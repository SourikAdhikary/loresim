"""Example 03: D&D Campaign 'Fog-of-War' Epistemic Player Portal View."""

from __future__ import annotations

import tempfile
from pathlib import Path

from loresim import LoreSimEngine


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        engine = LoreSimEngine(Path(tmp), world_name="DnDFogOfWar")
        engine.seed_demo_mystery_world()

        for char_id in ("vance", "clara", "kael", "thorne"):
            ctx = engine.firewall.compile_agent_context(char_id, query_tick=4)
            print(ctx["prompt_text"])
            print("-" * 60)
        engine.close()


if __name__ == "__main__":
    main()
