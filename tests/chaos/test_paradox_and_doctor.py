"""Chaos & invariant tests: branch paradoxes, strict traps, and all 12 LoreSimDoctor checks."""

from __future__ import annotations

import pytest

from loresim.core.errors import ParadoxError, TeleportationViolationError
from loresim.interfaces.engine import LoreSimEngine


def test_doctor_all_twelve_invariants_pass(engine: LoreSimEngine) -> None:
    engine.seed_demo_mystery_world()
    results = engine.doctor.run_all_checks()
    assert len(results) == 12
    assert all(r.passed for r in results), [r for r in results if not r.passed]


def test_strict_mode_teleportation_and_branch_paradox(engine: LoreSimEngine) -> None:
    engine.seed_demo_mystery_world()
    with pytest.raises(TeleportationViolationError):
        engine.record_event(
            tick=6,
            story_time_minutes=106,  # Only 1 minute after tick 5 in great_hall!
            location_id="tavern",  # Requires 55 minutes from great_hall
            actor_id="vance",
            event_type="MOVE",
            strict_override=True,
        )

    engine.db.fork_branch("child_b", from_branch="main", fork_tick=3)
    with pytest.raises(ParadoxError):
        # Cannot fork a grandchild at tick 1 before parent's fork_tick 3
        engine.db.fork_branch("grandchild_b", from_branch="child_b", fork_tick=1)
