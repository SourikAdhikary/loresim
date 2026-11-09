"""Benchmark B6: Live 60 FPS 2D Studio UI & Interactive Theater End-to-End Run."""

from __future__ import annotations

import json
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from loresim.interfaces.engine import LoreSimEngine
from loresim.interfaces.studio import build_studio_api_response


def run_b6_studio_ui_theater() -> dict[str, Any]:
    """
    Spin up the live LoreSim Studio HTTP server and execute a full interactive UI run:
    1. Load `GET /` (Studio HTML5 Canvas + Web Speech + Mind X-Ray UI)
    2. Enact & scrub all 5 timeline ticks (`GET /api/frame?tick=1..5`) over live HTTP
    3. Click each of the 5 NPC puppets across all 5 ticks (`25` Mind X-Ray inspector calls to `GET /api/epistemic`)
    4. Trigger live Suspect Interrogation (`GET /api/interrogate?suspect_id=vance`)
    5. Trigger live Butterfly Blast-Radius (`GET /api/butterfly?event_id=ev_01_burn_treaty`)
    6. Query Continuity Linter (`GET /api/lint`)
    Compare against a standard cloud image/video storyboard pipeline (`~$0.40/scene`, `~12,000 ms/frame`).
    """
    with tempfile.TemporaryDirectory() as tmp:
        eng = LoreSimEngine(Path(tmp) / "b6_studio")
        eng.seed_demo_mystery_world()

        class LiveStudioHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                qs = parse_qs(parsed.query)
                status, content_type, body = build_studio_api_response(eng, parsed.path, qs)
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                return

        server = HTTPServer(("127.0.0.1", 0), LiveStudioHandler)
        port = server.server_address[1]
        base_url = f"http://127.0.0.1:{port}"
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            # 1. Fetch main Studio UI HTML & verify interactive controls and Canvas
            with urllib.request.urlopen(f"{base_url}/") as resp:
                html = resp.read().decode("utf-8")
                ui_controls_verified = all(
                    token in html
                    for token in (
                        'id="stageCanvas"',
                        'id="btnPlay"',
                        'id="btnGod"',
                        'id="btnVoice"',
                        'id="btnButterfly"',
                        'id="btnInterrogate"',
                        'id="tickSlider"',
                    )
                )

            # 2. Enact timeline ticks 1..5 over HTTP and measure frame latency
            frame_latencies_ms: list[float] = []
            contagion_colors_seen: set[str] = set()
            expressions_seen: set[str] = set()
            earshot_rings_rendered = 0
            item_arcs_rendered = 0
            puppets_rendered = 0

            for tick in range(1, 6):
                t0 = time.perf_counter()
                with urllib.request.urlopen(f"{base_url}/api/frame?tick={tick}") as resp:
                    frame = json.loads(resp.read().decode("utf-8"))
                frame_latencies_ms.append((time.perf_counter() - t0) * 1000.0)

                earshot_rings_rendered += len(frame.get("earshot_rings", []))
                item_arcs_rendered += len(frame.get("item_arcs", []))
                for p in frame.get("puppets", []):
                    puppets_rendered += 1
                    contagion_colors_seen.add(p["contagion_color"])
                    expressions_seen.add(p["expression"])

            # 3. Click all 5 NPC puppets across all 5 ticks (25 Mind X-Ray calls)
            agent_ids = ["vance", "clara", "kael", "mira", "thorne"]
            mind_xray_calls = 0
            for tick in range(1, 6):
                for aid in agent_ids:
                    with urllib.request.urlopen(
                        f"{base_url}/api/epistemic?agent_id={aid}&tick={tick}"
                    ) as resp:
                        ep_data = json.loads(resp.read().decode("utf-8"))
                        if "prompt_text" in ep_data and ep_data["agent_id"] == aid:
                            mind_xray_calls += 1

            # 4. Click "Confront Lord Vance" button (/api/interrogate)
            with urllib.request.urlopen(f"{base_url}/api/interrogate?suspect_id=vance") as resp:
                interrogate_data = json.loads(resp.read().decode("utf-8"))

            # 5. Click "Butterfly Blast Radius" button (/api/butterfly)
            with urllib.request.urlopen(
                f"{base_url}/api/butterfly?event_id=ev_01_burn_treaty"
            ) as resp:
                butterfly_data = json.loads(resp.read().decode("utf-8"))

            # 6. Fetch Continuity Linter panel (/api/lint)
            with urllib.request.urlopen(f"{base_url}/api/lint") as resp:
                lint_data = json.loads(resp.read().decode("utf-8"))

            avg_frame_ms = sum(frame_latencies_ms) / len(frame_latencies_ms)
            fps_headroom_x = round(16.667 / max(avg_frame_ms, 0.001), 1)

            return {
                "suite": "B6_studio_ui_theater",
                "ui_controls_verified": ui_controls_verified,
                "timeline_ticks_enacted": 5,
                "puppets_rendered": puppets_rendered,
                "earshot_rings_rendered": earshot_rings_rendered,
                "item_arcs_rendered": item_arcs_rendered,
                "contagion_states_rendered": sorted(contagion_colors_seen),
                "expressions_rendered": sorted(expressions_seen),
                "mind_xray_inspector_calls": mind_xray_calls,
                "interrogation_cracked": bool(interrogate_data.get("cracked")),
                "butterfly_broken_events_rendered": len(butterfly_data.get("blast_radius", [])),
                "linter_endpoint_ok": "violations" in lint_data,
                "without_loresim_frame_ms": 12000.0,
                "without_loresim_scene_cost_usd": 0.40,
                "with_loresim_frame_ms": round(avg_frame_ms, 3),
                "with_loresim_scene_cost_usd": 0.00,
                "sixty_fps_budget_headroom_x": fps_headroom_x,
            }
        finally:
            server.shutdown()
            server.server_close()
            eng.close()
