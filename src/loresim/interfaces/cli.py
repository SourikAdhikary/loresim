"""Command-line interface (`loresim`) for the LoreSim Epistemic World & Continuity Engine."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from loresim.core.rust_bridge import is_rust_kernel_loaded, rust_kernel_version
from loresim.interfaces.engine import LoreSimEngine
from loresim.interfaces.mcp_server import LoreSimMCPServer
from loresim.interfaces.studio import serve_studio


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="loresim",
        description="LoreSim: Hybrid Rust + Python Epistemic World, Continuity Compiler & 60 FPS NPC Stage Engine",
    )
    parser.add_argument(
        "--workspace",
        default=".",
        help="Path to the LoreSim workspace directory (default: current directory)",
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("init", help="Initialize a new LoreSim world and seed demo scenario")
    sub.add_parser("status", help="Display active world, branch, Rust kernel status, and head tick")
    sub.add_parser("doctor", help="Verify all 12 formal mathematical & relational kernel invariants")

    lint_p = sub.add_parser("lint", help="Run the 7-Rule Continuity & Plot-Hole Compiler")
    lint_p.add_argument("--branch", default="main")

    ep_p = sub.add_parser("epistemic", help="Inspect a character's isolated EpistemicVault B_a(t)")
    ep_p.add_argument("agent_id")
    ep_p.add_argument("--tick", type=int, default=None)
    ep_p.add_argument("--branch", default="main")

    bf_p = sub.add_parser("butterfly", help="Compute the Butterfly-Effect causal blast radius of disabling an event")
    bf_p.add_argument("event_id")
    bf_p.add_argument("--branch", default="main")

    st_p = sub.add_parser("stage", help="Compile a 60 FPS 2D NPC StageFrame JSON packet at (branch, tick)")
    st_p.add_argument("--tick", type=int, default=None)
    st_p.add_argument("--branch", default="main")

    int_p = sub.add_parser("interrogate", help="Cross-examine a suspect NPC with all known objective evidence")
    int_p.add_argument("suspect_id")

    studio_p = sub.add_parser("studio", help="Launch the 60 FPS 2D NPC Theater & Contagion Map Web Studio")
    studio_p.add_argument("--host", default="127.0.0.1")
    studio_p.add_argument("--port", type=int, default=8420)

    sub.add_parser("mcp", help="Run the JSON-RPC 2.0 MCP Server over stdio")

    args = parser.parse_args(argv)
    ws = Path(args.workspace).resolve()
    engine = LoreSimEngine(ws)

    try:
        if args.cmd == "init":
            info = engine.seed_demo_mystery_world()
            print(json.dumps(info, indent=2))
            return 0

        if args.cmd == "status":
            engine.seed_demo_mystery_world()
            payload = {
                "workspace": str(ws),
                "rust_kernel_loaded": is_rust_kernel_loaded(),
                "rust_kernel_version": rust_kernel_version(),
                "head_tick": engine.db.get_branch_head_tick("main"),
                "agents": [a.agent_id for a in engine.agents.list_agents()],
                "locations": [loc.location_id for loc in engine.spatial.list_locations()],
            }
            print(json.dumps(payload, indent=2))
            return 0

        if args.cmd == "doctor":
            engine.seed_demo_mystery_world()
            checks = engine.doctor.run_all_checks()
            passed_cnt = sum(1 for c in checks if c.passed)
            for c in checks:
                mark = "PASS" if c.passed else "FAIL"
                print(f"[{mark}] {c.code} ({c.name}): {c.detail}")
            print(f"\nLoreSim Doctor Summary: {passed_cnt}/{len(checks)} formal kernel invariants PASSED.")
            return 0 if passed_cnt == len(checks) else 1

        if args.cmd == "lint":
            engine.seed_demo_mystery_world()
            engine.linter.audit_dangling_threads(branch_ref=args.branch)
            vios = engine.linter.list_violations(branch_ref=args.branch)
            print(json.dumps([asdict(v) for v in vios], indent=2))
            return 0

        if args.cmd == "epistemic":
            engine.seed_demo_mystery_world()
            ctx = engine.firewall.compile_agent_context(
                args.agent_id, branch_ref=args.branch, query_tick=args.tick
            )
            print(ctx["prompt_text"])
            return 0

        if args.cmd == "butterfly":
            engine.seed_demo_mystery_world()
            blast = engine.butterfly.compute_blast_radius(args.event_id, branch_ref=args.branch)
            print(json.dumps([asdict(b) for b in blast], indent=2))
            return 0

        if args.cmd == "stage":
            engine.seed_demo_mystery_world()
            frame = engine.get_stage_frame(branch_ref=args.branch, tick=args.tick)
            print(json.dumps(asdict(frame), indent=2))
            return 0

        if args.cmd == "interrogate":
            engine.seed_demo_mystery_world()
            facts = engine.vault.list_visible_facts()
            truth_ids = [f.fact_id for f in facts if f.objective_truth]
            res = engine.simulator.interrogate_suspect(args.suspect_id, truth_ids)
            print(json.dumps(res, indent=2))
            return 0

        if args.cmd == "studio":
            serve_studio(engine, host=args.host, port=args.port)
            return 0

        if args.cmd == "mcp":
            LoreSimMCPServer(engine).serve_stdio()
            return 0

        parser.print_help()
        return 0
    finally:
        engine.close()


if __name__ == "__main__":
    sys.exit(main())
