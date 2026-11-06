"""Example 04: Butterfly-Effect Causal Blast-Radius Tracer & Counterfactual Branching."""

from __future__ import annotations

import tempfile
from pathlib import Path

from loresim import LoreSimEngine


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        engine = LoreSimEngine(Path(tmp), world_name="ButterflySim")
        engine.seed_demo_mystery_world()

        blast = engine.butterfly.compute_blast_radius("ev_01_burn_treaty")
        print("Disabling Tick 1 ('ev_01_burn_treaty') breaks the following downstream scenes:")
        for item in blast:
            print(f"  - [Tick {item.tick}] {item.broken_event_id}: {item.broken_reason} (chain={item.causal_chain})")
        engine.close()


if __name__ == "__main__":
    main()
