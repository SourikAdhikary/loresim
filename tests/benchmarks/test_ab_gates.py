"""A/B Benchmark regression gates verifying `With LoreSim` beats `Without LoreSim` across B1..B5 & S1..S4."""

from __future__ import annotations

from benchmarks.runner import run_all_benchmarks


def test_all_ab_benchmark_gates() -> None:
    results = run_all_benchmarks(write_markdown=False)
    suites = results["suites"]

    # B1: 0% secret leak rate and 100% false-belief fidelity
    assert suites["B1"]["with_loresim_secret_leak_pct"] == 0.0
    assert suites["B1"]["without_loresim_secret_leak_pct"] >= 80.0
    assert suites["B1"]["with_loresim_false_belief_fidelity_pct"] == 100.0

    # B2: 100% plot-hole recall and precision across all 7 continuity rules
    assert suites["B2"]["with_loresim_recall_pct"] == 100.0
    assert suites["B2"]["with_loresim_precision_pct"] == 100.0

    # B3: 100% contagion classification & firsthand lie exposure
    assert suites["B3"]["with_loresim_contagion_accuracy_pct"] == 100.0
    assert suites["B3"]["with_loresim_lie_exposure_recall_pct"] == 100.0

    # B4: >100x tick speedup and >95% token reduction
    assert suites["B4"]["tick_speedup_x"] >= 100.0
    assert suites["B4"]["token_reduction_pct"] >= 95.0
    assert suites["B4"]["stage_frames_compiled"] == 100

    # B5: 100% Butterfly-Effect blast-radius recall and 0% cross-branch contamination
    assert suites["B5"]["blast_radius_recall_pct"] == 100.0
    assert suites["B5"]["cross_branch_contamination_pct"] == 0.0

    # S1..S4 Narrative Traps
    for trap in results["traps"]:
        assert trap["passed"] is True, f"Trap failed: {trap}"
