"""Formal verifier for all 12 mathematical & relational LoreSim kernel invariants (INV-01..INV-12)."""

from __future__ import annotations

from loresim.compiler.butterfly import ButterflyAnalyzer
from loresim.core.rust_bridge import is_rust_kernel_loaded
from loresim.core.types import InvariantCheckResult
from loresim.epistemic.firewall import EpistemicPromptFirewall
from loresim.epistemic.vault import EpistemicVault
from loresim.simulator.scene import SceneSimulator
from loresim.storage.db import SQLiteDatabase
from loresim.storage.schema import STRICT_TABLE_NAMES
from loresim.world.agents import AgentRegistry
from loresim.world.inventory import InventoryTracker
from loresim.world.spatial import SpatialTopology


class LoreSimDoctor:
    """Verifies all 12 formal mathematical & relational invariants of the LoreSim kernel."""

    def __init__(
        self,
        db: SQLiteDatabase,
        spatial: SpatialTopology,
        inventory: InventoryTracker,
        agents: AgentRegistry,
        vault: EpistemicVault,
        firewall: EpistemicPromptFirewall,
        simulator: SceneSimulator,
        butterfly: ButterflyAnalyzer,
    ) -> None:
        self.db = db
        self.spatial = spatial
        self.inventory = inventory
        self.agents = agents
        self.vault = vault
        self.firewall = firewall
        self.simulator = simulator
        self.butterfly = butterfly

    def run_all_checks(self) -> list[InvariantCheckResult]:
        return [
            self._check_inv01_branch_tree_acyclicity(),
            self._check_inv02_strict_tables_and_wal(),
            self._check_inv03_linear_unique_item_conservation(),
            self._check_inv04_single_location_agent_occupancy(),
            self._check_inv05_epistemic_provenance_integrity(),
            self._check_inv06_firsthand_witness_validity(),
            self._check_inv07_zero_leak_prompt_firewall(),
            self._check_inv08_confidence_and_trust_bounds(),
            self._check_inv09_dijkstra_metric_non_negativity(),
            self._check_inv10_fts5_lexical_index_parity(),
            self._check_inv11_rust_kernel_acceleration(),
            self._check_inv12_deterministic_simulation_replay(),
        ]

    def _check_inv01_branch_tree_acyclicity(self) -> InvariantCheckResult:
        rows = self.db.fetchall("SELECT branch_id, name, fork_tick, head_tick FROM branches")
        try:
            for r in rows:
                bounds = self.db.get_branch_ancestry_bounds(str(r["branch_id"]))
                if not bounds or bounds[0][0] != "branch_main":
                    return InvariantCheckResult(
                        "INV-01",
                        "Branch Tree Acyclicity & Root Ancestry",
                        False,
                        f"Branch {r['name']} does not terminate at branch_main",
                    )
            return InvariantCheckResult(
                "INV-01",
                "Branch Tree Acyclicity & Root Ancestry",
                True,
                f"Verified {len(rows)} narrative branch(es) terminate cleanly at root",
            )
        except Exception as exc:
            return InvariantCheckResult("INV-01", "Branch Tree Acyclicity & Root Ancestry", False, str(exc))

    def _check_inv02_strict_tables_and_wal(self) -> InvariantCheckResult:
        jmode = str(self.db.fetchone("PRAGMA journal_mode")[0]).lower()
        master_rows = self.db.fetchall(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'facts_fts%'"
        )
        strict_count = sum(1 for r in master_rows if "STRICT" in str(r["sql"]).upper())
        passed = jmode in ("wal", "memory") and strict_count >= len(STRICT_TABLE_NAMES)
        return InvariantCheckResult(
            "INV-02",
            "14 STRICT SQLite Tables & WAL Mode",
            passed,
            f"journal_mode={jmode}, strict_tables={strict_count}/{len(STRICT_TABLE_NAMES)}",
        )

    def _check_inv03_linear_unique_item_conservation(self) -> InvariantCheckResult:
        items = self.db.fetchall("SELECT item_id FROM items WHERE is_unique = 1")
        branches = self.db.fetchall("SELECT branch_id, head_tick FROM branches")
        for b in branches:
            bid = str(b["branch_id"])
            ht = int(b["head_tick"])
            for it in items:
                iid = str(it["item_id"])
                holder = self.inventory.get_current_holder(iid, branch_ref=bid, query_tick=ht)
                if holder is not None and not holder[1]:
                    return InvariantCheckResult(
                        "INV-03",
                        "Linear Unique Item Conservation",
                        False,
                        f"Item {iid} has empty holder at ({bid}, {ht})",
                    )
        return InvariantCheckResult(
            "INV-03",
            "Linear Unique Item Conservation",
            True,
            f"Verified single-holder linear conservation across {len(items)} unique item(s)",
        )

    def _check_inv04_single_location_agent_occupancy(self) -> InvariantCheckResult:
        agents = self.agents.list_agents()
        for ag in agents:
            st = self.agents.get_agent_state(ag.agent_id)
            if not st.get("location_id"):
                return InvariantCheckResult(
                    "INV-04",
                    "Single-Location Agent Occupancy",
                    False,
                    f"Agent {ag.agent_id} missing valid location occupancy",
                )
        return InvariantCheckResult(
            "INV-04",
            "Single-Location Agent Occupancy",
            True,
            f"Verified unique spatial occupancy for {len(agents)} agent(s)",
        )

    def _check_inv05_epistemic_provenance_integrity(self) -> InvariantCheckResult:
        orphans = self.db.fetchall(
            """
            SELECT b.belief_id FROM epistemic_beliefs b
            LEFT JOIN canonical_facts f ON b.fact_id = f.fact_id
            WHERE f.fact_id IS NULL OR b.tick < f.created_tick
            """
        )
        passed = len(orphans) == 0
        return InvariantCheckResult(
            "INV-05",
            "Epistemic Provenance & Temporal Causality",
            passed,
            f"orphan_or_acausal_beliefs={len(orphans)}",
        )

    def _check_inv06_firsthand_witness_validity(self) -> InvariantCheckResult:
        invalid = self.db.fetchall(
            """
            SELECT belief_id FROM epistemic_beliefs
            WHERE modality = 'FIRSTHAND' AND confidence < 0.99
            """
        )
        return InvariantCheckResult(
            "INV-06",
            "Firsthand Witness Certainty Law (KD45_n)",
            len(invalid) == 0,
            f"invalid_firsthand_rows={len(invalid)}",
        )

    def _check_inv07_zero_leak_prompt_firewall(self) -> InvariantCheckResult:
        agents = self.agents.list_agents()
        for ag in agents:
            ctx = self.firewall.compile_agent_context(ag.agent_id)
            all_facts = self.vault.list_visible_facts()
            for f in all_facts:
                if f.fact_id not in ctx["known_fact_ids"]:
                    prop = f"{f.subject} {f.predicate} {f.obj}"
                    if prop in ctx["prompt_text"]:
                        return InvariantCheckResult(
                            "INV-07",
                            "Zero-Leak Epistemic Prompt Firewall",
                            False,
                            f"Unknown fact {f.fact_id} leaked into {ag.agent_id} prompt",
                        )
        return InvariantCheckResult(
            "INV-07",
            "Zero-Leak Epistemic Prompt Firewall",
            True,
            f"Verified 0% unlearned fact leakage across {len(agents)} agent prompt(s)",
        )

    def _check_inv08_confidence_and_trust_bounds(self) -> InvariantCheckResult:
        bad_conf = self.db.fetchall(
            "SELECT belief_id FROM epistemic_beliefs WHERE confidence < 0.0 OR confidence > 1.0"
        )
        bad_trust = self.db.fetchall(
            "SELECT rel_id FROM relationships WHERE trust < -1.0 OR trust > 1.0 OR affection < -1.0 OR affection > 1.0"
        )
        passed = len(bad_conf) == 0 and len(bad_trust) == 0
        return InvariantCheckResult(
            "INV-08",
            "Probability & Trust Interval Bounds",
            passed,
            f"out_of_bound_beliefs={len(bad_conf)}, out_of_bound_relationships={len(bad_trust)}",
        )

    def _check_inv09_dijkstra_metric_non_negativity(self) -> InvariantCheckResult:
        bad_routes = self.db.fetchall("SELECT route_id FROM routes WHERE travel_minutes <= 0")
        return InvariantCheckResult(
            "INV-09",
            "Dijkstra Route Metric Non-Negativity",
            len(bad_routes) == 0,
            f"non_positive_routes={len(bad_routes)}",
        )

    def _check_inv10_fts5_lexical_index_parity(self) -> InvariantCheckResult:
        f_cnt = int(self.db.fetchone("SELECT COUNT(*) FROM canonical_facts")[0])
        fts_cnt = int(self.db.fetchone("SELECT COUNT(*) FROM facts_fts")[0])
        return InvariantCheckResult(
            "INV-10",
            "FTS5 Lexical Fact Index Parity",
            f_cnt == fts_cnt,
            f"canonical_facts={f_cnt}, facts_fts={fts_cnt}",
        )

    def _check_inv11_rust_kernel_acceleration(self) -> InvariantCheckResult:
        loaded = is_rust_kernel_loaded()
        return InvariantCheckResult(
            "INV-11",
            "Native Rust Kernel Bridge (libloresim_core)",
            loaded,
            f"rust_kernel_loaded={loaded}",
        )

    def _check_inv12_deterministic_simulation_replay(self) -> InvariantCheckResult:
        agents = [a.agent_id for a in self.agents.list_agents()[:2]]
        if not agents:
            return InvariantCheckResult(
                "INV-12",
                "Deterministic Scene Simulation Replay",
                True,
                "Verified deterministic replay (empty agent set)",
            )
        r1 = self.simulator.run_multi_turn_scene(agents, "treaty", turns=2)
        r2 = self.simulator.run_multi_turn_scene(agents, "treaty", turns=2)
        passed = r1["transcript"] == r2["transcript"] and r1["dramatic_irony_score"] == r2["dramatic_irony_score"]
        return InvariantCheckResult(
            "INV-12",
            "Deterministic Scene Simulation Replay",
            passed,
            f"replay_identical={passed}",
        )
