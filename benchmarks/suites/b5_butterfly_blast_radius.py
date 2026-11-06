"""B5: Counterfactual 'Butterfly Effect' Blast Radius & Narrative Branching Benchmark."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any

from loresim.interfaces.engine import LoreSimEngine


def run_b5_butterfly_blast_radius() -> dict[str, Any]:
    """Evaluate:
    1. Causal Blast-Radius accuracy & latency when disabling a root Chapter 1 event across a 40-event chain.
    2. O(1) Counterfactual narrative branch forking latency & 0% cross-branch epistemic contamination.
    """
    with tempfile.TemporaryDirectory() as tmp:
        engine = LoreSimEngine(Path(tmp), world_name="B5_Butterfly")
        try:
            engine.spatial.add_location("vault", "Vault", x_coord=150.0, y_coord=150.0)
            engine.spatial.add_location("keep", "Keep", x_coord=400.0, y_coord=150.0)
            for i in range(6):
                engine.agents.register_agent(f"agent_{i}", f"Agent {i}", initial_location_id="vault", tick=0)

            # Root event at tick 1 (`ev_root`) that 15 downstream events causally depend on
            engine.record_event(
                event_id="ev_root",
                tick=1,
                location_id="vault",
                actor_id="agent_0",
                event_type="WITNESS_ACTION",
                claims=({"subject": "agent_0", "predicate": "found", "object": "master_key"},),
            )

            expected_broken = 15
            prev_dep = "ev_root"
            for idx in range(2, 42):
                eid = f"ev_{idx}"
                if idx <= 16:
                    # 15 events form a causal dependency chain on ev_root
                    engine.record_event(
                        event_id=eid,
                        tick=idx,
                        location_id="vault",
                        actor_id=f"agent_{idx % 6}",
                        event_type="ACTION",
                        preconditions={"requires_events": [prev_dep]},
                        summary=f"Causal chain step {idx}",
                    )
                    prev_dep = eid
                else:
                    # 25 independent subplot events
                    engine.record_event(
                        event_id=eid,
                        tick=idx,
                        location_id="keep",
                        actor_id=f"agent_{idx % 6}",
                        event_type="ACTION",
                        summary=f"Independent subplot event {idx}",
                    )

            t0 = time.perf_counter()
            blast = engine.butterfly.compute_blast_radius("ev_root")
            blast_ms = round((time.perf_counter() - t0) * 1000.0, 3)

            recall_pct = round((len(blast) / expected_broken) * 100.0, 1)

            # Fork 30 counterfactual "What-If" branches at tick 10 and test cross-branch isolation
            t_fork0 = time.perf_counter()
            for b_idx in range(30):
                b_name = f"what_if_{b_idx}"
                engine.db.fork_branch(b_name, from_branch="main", fork_tick=10)
                engine.record_event(
                    tick=11,
                    location_id="keep",
                    actor_id="agent_1",
                    event_type="WITNESS_ACTION",
                    visibility="STEALTH",
                    is_secret=True,
                    claims=({"subject": "agent_1", "predicate": "triggered", "object": f"branch_secret_{b_idx}"},),
                    branch_ref=b_name,
                )
            avg_fork_ms = round(((time.perf_counter() - t_fork0) * 1000.0) / 30.0, 3)

            # Verify `main` branch has 0% contamination from any of the 30 `what_if_*` branches
            main_facts = {f.obj for f in engine.vault.list_visible_facts(branch_ref="main")}
            contaminated = sum(1 for b_idx in range(30) if f"branch_secret_{b_idx}" in main_facts)

            return {
                "suite": "B5",
                "name": "Butterfly-Effect Blast Radius & 30-Branch Counterfactual Forking",
                "expected_broken_events": expected_broken,
                "detected_broken_events": len(blast),
                "blast_radius_recall_pct": recall_pct,
                "blast_radius_latency_ms": blast_ms,
                "avg_branch_fork_latency_ms": avg_fork_ms,
                "cross_branch_contamination_pct": round((contaminated / 30.0) * 100.0, 1),
            }
        finally:
            engine.close()
