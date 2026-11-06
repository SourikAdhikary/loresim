"""Zero-dependency HTTP/JSON Studio Server for the 60 FPS 2D NPC Epistemic Theater."""

from __future__ import annotations

import json
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from loresim.interfaces.engine import LoreSimEngine


def build_studio_api_response(engine: LoreSimEngine, path: str, query: dict[str, list[str]]) -> tuple[int, str, bytes]:
    """Pure request router used by both the live HTTP server and unit/integration tests."""
    if path in ("/", "/index.html"):
        html_path = Path(__file__).with_name("studio_ui.html")
        return 200, "text/html; charset=utf-8", html_path.read_bytes()

    if path == "/api/frame":
        tick_str = query.get("tick", [None])[0]
        branch = query.get("branch", ["main"])[0]
        tick = int(tick_str) if tick_str is not None else None
        frame = engine.get_stage_frame(branch_ref=branch, tick=tick)
        return 200, "application/json", json.dumps(asdict(frame)).encode("utf-8")

    if path == "/api/epistemic":
        agent_id = query.get("agent_id", ["vance"])[0]
        tick_str = query.get("tick", [None])[0]
        tick = int(tick_str) if tick_str is not None else None
        ctx = engine.firewall.compile_agent_context(agent_id, query_tick=tick)
        ctx["known_fact_ids"] = sorted(ctx["known_fact_ids"])
        return 200, "application/json", json.dumps(ctx).encode("utf-8")

    if path == "/api/interrogate":
        suspect_id = query.get("suspect_id", ["vance"])[0]
        facts = engine.vault.list_visible_facts()
        truth_ids = [f.fact_id for f in facts if f.objective_truth]
        res = engine.simulator.interrogate_suspect(suspect_id, truth_ids)
        return 200, "application/json", json.dumps(res).encode("utf-8")

    if path == "/api/butterfly":
        ev_id = query.get("event_id", ["ev_01_burn_treaty"])[0]
        blast = engine.butterfly.compute_blast_radius(ev_id)
        payload = {"disabled_event_id": ev_id, "blast_radius": [asdict(b) for b in blast]}
        return 200, "application/json", json.dumps(payload).encode("utf-8")

    if path == "/api/lint":
        vios = engine.linter.list_violations()
        payload = {"count": len(vios), "violations": [asdict(v) for v in vios]}
        return 200, "application/json", json.dumps(payload).encode("utf-8")

    return 404, "application/json", json.dumps({"error": f"Not found: {path}"}).encode("utf-8")


def serve_studio(engine: LoreSimEngine, host: str = "127.0.0.1", port: int = 8420) -> None:
    """Start the local LoreSim 60 FPS NPC Theater Studio server."""
    engine.seed_demo_mystery_world()

    class StudioHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            status, content_type, body = build_studio_api_response(engine, parsed.path, qs)
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

    server = HTTPServer((host, port), StudioHandler)
    print(f"🎭 LoreSim 60 FPS 2D NPC Studio running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
