"""JSON-RPC 2.0 MCP Server exposing 9 LoreSim tools for external game, writing, and DM hosts."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from typing import Any

from loresim.interfaces.engine import LoreSimEngine

MCP_TOOLS_SCHEMA = [
    {
        "name": "loresim_record_event",
        "description": "Record a world event at (branch, tick) with automatic continuity linting and epistemic belief propagation.",
    },
    {
        "name": "loresim_query_epistemic",
        "description": "Inspect a character's strictly isolated EpistemicVault B_a(b, t) (known truths, believed lies, withheld secrets).",
    },
    {
        "name": "loresim_lint_continuity",
        "description": "Run all 7 Continuity & Plot-Hole Compiler rules (LINT-01..LINT-07) on the timeline.",
    },
    {
        "name": "loresim_butterfly_blast_radius",
        "description": "Compute the causal and epistemic blast radius when a historical event is disabled.",
    },
    {
        "name": "loresim_stage_frame",
        "description": "Compile a 60 FPS 2D NPC Puppet StageFrame (positions, expressions, earshot rings, item arcs, irony score).",
    },
    {
        "name": "loresim_interrogate",
        "description": "Cross-examine a suspect NPC with evidence fact IDs and track composure collapse.",
    },
    {
        "name": "loresim_simulate_scene",
        "description": "Run a multi-turn epistemically sandboxed conversation among characters at (branch, tick).",
    },
    {
        "name": "loresim_fork_branch",
        "description": "Fork an O(1) counterfactual narrative 'What-If' branch at any historical tick.",
    },
    {
        "name": "loresim_doctor",
        "description": "Verify all 12 formal mathematical & relational kernel invariants (INV-01..INV-12).",
    },
]


class LoreSimMCPServer:
    """JSON-RPC 2.0 MCP handler over stdio or direct request dispatch."""

    def __init__(self, engine: LoreSimEngine) -> None:
        self.engine = engine

    def handle_request(self, req: dict[str, Any]) -> dict[str, Any]:
        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params") or {}

        try:
            if method == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {"name": "loresim-mcp", "version": "0.1.0"},
                        "capabilities": {"tools": {}},
                    },
                }
            if method == "tools/list":
                return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": MCP_TOOLS_SCHEMA}}
            if method == "tools/call":
                tool_name = params.get("name", "")
                args = params.get("arguments") or {}
                out = self._dispatch_tool(tool_name, args)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(out)}], "data": out},
                }
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown method: {method}"},
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": str(exc)},
            }

    def _dispatch_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "loresim_record_event":
            ev, vios = self.engine.record_event(
                tick=int(args["tick"]),
                location_id=str(args["location_id"]),
                actor_id=str(args["actor_id"]),
                event_type=str(args.get("event_type", "WITNESS_ACTION")),
                target_ids=args.get("target_ids", []),
                summary=str(args.get("summary", "")),
                raw_text=str(args.get("raw_text", "")),
                claims=args.get("claims", []),
                item_id=args.get("item_id"),
                is_secret=bool(args.get("is_secret", False)),
                branch_ref=str(args.get("branch", "main")),
            )
            return {"event": asdict(ev), "violations": [asdict(v) for v in vios]}

        if name == "loresim_query_epistemic":
            ctx = self.engine.firewall.compile_agent_context(
                agent_id=str(args["agent_id"]),
                branch_ref=str(args.get("branch", "main")),
                query_tick=args.get("tick"),
            )
            ctx["known_fact_ids"] = sorted(ctx["known_fact_ids"])
            return ctx

        if name == "loresim_lint_continuity":
            branch = str(args.get("branch", "main"))
            tick = args.get("tick")
            self.engine.linter.audit_dangling_threads(branch_ref=branch, current_tick=tick)
            vios = self.engine.linter.list_violations(branch_ref=branch, query_tick=tick)
            return {"violations": [asdict(v) for v in vios], "count": len(vios)}

        if name == "loresim_butterfly_blast_radius":
            items = self.engine.butterfly.compute_blast_radius(
                disabled_event_id=str(args["event_id"]),
                branch_ref=str(args.get("branch", "main")),
            )
            return {"disabled_event_id": args["event_id"], "blast_radius": [asdict(i) for i in items]}

        if name == "loresim_stage_frame":
            frame = self.engine.get_stage_frame(
                branch_ref=str(args.get("branch", "main")),
                tick=args.get("tick"),
                focus_fact_id=args.get("focus_fact_id"),
            )
            return asdict(frame)

        if name == "loresim_interrogate":
            return self.engine.simulator.interrogate_suspect(
                suspect_id=str(args["suspect_id"]),
                presented_fact_ids=list(args.get("evidence_fact_ids", [])),
                branch_ref=str(args.get("branch", "main")),
                query_tick=args.get("tick"),
            )

        if name == "loresim_simulate_scene":
            return self.engine.simulator.run_multi_turn_scene(
                participant_ids=list(args["participants"]),
                topic_query=str(args.get("topic", "")),
                turns=int(args.get("turns", 4)),
                branch_ref=str(args.get("branch", "main")),
                query_tick=args.get("tick"),
            )

        if name == "loresim_fork_branch":
            bid = self.engine.db.fork_branch(
                new_name=str(args["name"]),
                from_branch=str(args.get("from_branch", "main")),
                fork_tick=args.get("fork_tick"),
            )
            return {"branch_id": bid, "name": args["name"]}

        if name == "loresim_doctor":
            results = self.engine.doctor.run_all_checks()
            return {
                "all_passed": all(r.passed for r in results),
                "checks": [asdict(r) for r in results],
            }

        raise ValueError(f"Unknown MCP tool: {name}")

    def serve_stdio(self) -> None:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            req = json.loads(line)
            resp = self.handle_request(req)
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
