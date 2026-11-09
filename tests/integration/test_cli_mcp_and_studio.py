"""End-to-end integration tests for CLI, JSON-RPC 2.0 MCP Server, and 60 FPS Studio HTTP Router."""

from __future__ import annotations

import json
from pathlib import Path

from loresim.interfaces.cli import main as cli_main
from loresim.interfaces.engine import LoreSimEngine
from loresim.interfaces.mcp_server import LoreSimMCPServer
from loresim.interfaces.studio import build_studio_api_response


def test_mcp_server_all_tools(engine: LoreSimEngine) -> None:
    engine.seed_demo_mystery_world()
    mcp = LoreSimMCPServer(engine)

    init_resp = mcp.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert init_resp["result"]["serverInfo"]["name"] == "loresim-mcp"

    list_resp = mcp.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert len(list_resp["result"]["tools"]) == 9

    frame_resp = mcp.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "loresim_stage_frame", "arguments": {"tick": 3}},
        }
    )
    assert frame_resp["result"]["data"]["tick"] == 3

    interrogate_resp = mcp.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "loresim_interrogate",
                "arguments": {
                    "suspect_id": "vance",
                    "evidence_fact_ids": [f.fact_id for f in engine.vault.list_visible_facts()],
                },
            },
        }
    )
    assert interrogate_resp["result"]["data"]["cracked"] is True


def test_studio_api_router_and_cli(tmp_path: Path) -> None:
    ws = tmp_path / "cli_ws"
    assert cli_main(["--workspace", str(ws), "init"]) == 0
    assert cli_main(["--workspace", str(ws), "doctor"]) == 0

    eng = LoreSimEngine(ws)
    try:
        status, ctype, body = build_studio_api_response(eng, "/", {})
        assert status == 200
        assert "text/html" in ctype
        assert b"LoreSim Studio" in body

        status, _, frame_bytes = build_studio_api_response(eng, "/api/frame", {"tick": ["3"]})
        assert status == 200
        frame_data = json.loads(frame_bytes.decode("utf-8"))
        assert len(frame_data["puppets"]) == 5
    finally:
        eng.close()


def test_live_studio_ui_interactive_theater_run() -> None:
    """Spin up the live HTTP Studio server and verify all UI Canvas, Mind X-Ray, Interrogation, and Butterfly flows."""
    from benchmarks.suites.b6_studio_ui_theater import run_b6_studio_ui_theater

    b6 = run_b6_studio_ui_theater()
    assert b6["ui_controls_verified"] is True
    assert b6["timeline_ticks_enacted"] == 5
    assert b6["puppets_rendered"] == 25
    assert b6["earshot_rings_rendered"] >= 4
    assert b6["item_arcs_rendered"] >= 1
    assert set(b6["contagion_states_rendered"]) >= {"GOLD_DECEIVER", "RED_LIE", "GREY_UNAWARE"}
    assert b6["mind_xray_inspector_calls"] == 25
    assert b6["interrogation_cracked"] is True
    assert b6["butterfly_broken_events_rendered"] >= 3
    assert b6["linter_endpoint_ok"] is True
    assert b6["with_loresim_frame_ms"] < 16.67
