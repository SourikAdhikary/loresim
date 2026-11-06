"""Two-pass stateful Markdown / Story-DSL script ingester."""

from __future__ import annotations

from typing import Any

from loresim.core.clock import parse_story_time_to_minutes


class ManuscriptIngester:
    """Parses structured Markdown / Story-DSL scripts into canonical event dictionaries.

    Supported directive syntax per line:
      `@tick 10 | Day 1, 09:00 | Ch1 | study | vance | WITNESS_ACTION | target=clara | claim=vance:burned:treaty | text=Vance burned the treaty.`
    """

    def parse_script_lines(self, script_text: str) -> list[dict[str, Any]]:
        parsed: list[dict[str, Any]] = []
        auto_tick = 1
        for raw_line in script_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("@tick"):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) < 6:
                    continue
                tick_num = int(parts[0].replace("@tick", "").strip() or auto_tick)
                time_str = parts[1]
                chapter_ref = parts[2]
                location_id = parts[3]
                actor_id = parts[4]
                event_type = parts[5]
                kwargs: dict[str, Any] = {}
                for kv in parts[6:]:
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        kwargs[k.strip()] = v.strip()

                targets = [t.strip() for t in kwargs.get("target", "").split(",") if t.strip()]
                claims: list[dict[str, Any]] = []
                if "claim" in kwargs:
                    for c_str in kwargs["claim"].split(";"):
                        c_parts = [x.strip() for x in c_str.split(":")]
                        if len(c_parts) == 3:
                            claims.append(
                                {
                                    "subject": c_parts[0],
                                    "predicate": c_parts[1],
                                    "object": c_parts[2],
                                }
                            )
                parsed.append(
                    {
                        "tick": tick_num,
                        "story_time_minutes": parse_story_time_to_minutes(time_str, tick_num),
                        "chapter_ref": chapter_ref,
                        "location_id": location_id,
                        "actor_id": actor_id,
                        "event_type": event_type,
                        "target_ids": targets,
                        "visibility": kwargs.get("vis", "PUBLIC_HERE"),
                        "item_id": kwargs.get("item"),
                        "claims": claims,
                        "summary": kwargs.get("text", f"{actor_id} -> {event_type} at {location_id}"),
                        "raw_text": kwargs.get("text", ""),
                    }
                )
                auto_tick = tick_num + 1
        return parsed
