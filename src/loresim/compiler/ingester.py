"""Multi-format stateful Manuscript Ingester (@tick DSL, Fountain Screenplay, Natural Prose, & LLM JSON)."""

from __future__ import annotations

import json
import re
from typing import Any

from loresim.core.clock import parse_story_time_to_minutes
from loresim.core.llm import LLMProvider, resolve_llm_provider_from_env
from loresim.world.agents import AgentRegistry
from loresim.world.inventory import InventoryTracker
from loresim.world.spatial import SpatialTopology


class ManuscriptIngester:
    """Parses structured `@tick` Story-DSL scripts, Fountain screenplays, and natural-language
    Markdown prose into canonical `LoreSimEngine` event dictionaries.
    """

    def __init__(
        self,
        spatial: SpatialTopology | None = None,
        agents: AgentRegistry | None = None,
        inventory: InventoryTracker | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self.spatial = spatial
        self.agents = agents
        self.inventory = inventory
        self.llm_provider: LLMProvider | None = llm_provider or resolve_llm_provider_from_env()

    def _build_lookup_maps(self) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
        """Build case-insensitive alias -> canonical ID maps for agents, items, and locations."""
        agent_map: dict[str, str] = {
            "lord vance": "vance",
            "chancellor vance": "vance",
            "vance": "vance",
            "lady clara": "clara",
            "ambassador clara": "clara",
            "clara": "clara",
            "captain kael": "kael",
            "kael": "kael",
            "spymaster mira": "mira",
            "mira": "mira",
            "general thorne": "thorne",
            "thorne": "thorne",
        }
        item_map: dict[str, str] = {
            "royal peace treaty": "royal_treaty",
            "peace treaty": "royal_treaty",
            "royal treaty": "royal_treaty",
            "valen signet dagger": "signet_dagger",
            "signet dagger": "signet_dagger",
            "vault cipher key": "cipher_key",
            "cipher key": "cipher_key",
        }
        loc_map: dict[str, str] = {
            "royal study": "study",
            "study": "study",
            "great banquet hall": "great_hall",
            "banquet hall": "great_hall",
            "great hall": "great_hall",
            "citadel courtyard": "courtyard",
            "courtyard": "courtyard",
            "harbor tavern": "tavern",
            "tavern": "tavern",
        }
        if self.agents is not None:
            for ag in self.agents.list_agents():
                agent_map[ag.agent_id.lower()] = ag.agent_id
                if ag.name:
                    agent_map[ag.name.lower()] = ag.agent_id
                    parts = ag.name.lower().split()
                    if len(parts) >= 2:
                        agent_map[parts[-1]] = ag.agent_id
        if self.inventory is not None:
            for row in self.inventory.db.fetchall("SELECT item_id, name FROM items"):
                iid = str(row["item_id"])
                name = str(row["name"]).lower()
                item_map[iid.lower()] = iid
                item_map[iid.lower().replace("_", " ")] = iid
                item_map[name] = iid
                words = name.split()
                if len(words) >= 3:
                    item_map[" ".join(words[-2:])] = iid
        if self.spatial is not None:
            for loc in self.spatial.list_locations():
                loc_map[loc.location_id.lower()] = loc.location_id
                loc_map[loc.name.lower()] = loc.location_id
        return agent_map, item_map, loc_map

    @staticmethod
    def _resolve_token(raw: str, mapping: dict[str, str]) -> str:
        cleaned = re.sub(r"^(the|a|an)\s+", "", raw.strip(), flags=re.IGNORECASE).strip(" .,!?;:\"'")
        low = cleaned.lower()
        if low in mapping:
            return mapping[low]
        for alias in sorted(mapping.keys(), key=len, reverse=True):
            if alias and re.search(rf"\b{re.escape(alias)}\b", low):
                return mapping[alias]
        return re.sub(r"[^a-z0-9_]+", "_", low).strip("_") or "unknown"

    @staticmethod
    def _extract_claim_from_clause(
        clause: str,
        agent_map: dict[str, str],
        item_map: dict[str, str],
        is_secret: bool = False,
    ) -> dict[str, Any] | None:
        cleaned = clause.strip().strip(".,!?;:\"'")
        if not cleaned:
            return None
        # Support explicit colon triple: `vance:burned:royal_treaty`
        if cleaned.count(":") == 2 and " " not in cleaned:
            s, p, o = [x.strip() for x in cleaned.split(":")]
            return {"subject": s, "predicate": p, "object": o, "is_secret": is_secret}

        verb_patterns = [
            (r"\b(?:secretly\s+)?(burned|burnt|incinerated|torched|destroyed)\b", "burned"),
            (r"\b(stole|stolen|pilfered|robbed)\b", "stole"),
            (r"\b(poisoned|laced|contaminated)\b", "poisoned"),
            (r"\b(killed|murdered|assassinated|stabbed)\b", "killed"),
            (r"\b(holds|holding|carrying|possesses|hid|concealed)\b", "holds"),
            (r"\b(forged|fabricated|faked)\b", "forged"),
        ]
        for pat, canonical_pred in verb_patterns:
            m = re.search(pat, cleaned, flags=re.IGNORECASE)
            if m:
                left = cleaned[: m.start()].strip()
                right = cleaned[m.end() :].strip()
                # Strip trailing witness clause from right side if present
                right = re.split(r"\b(?:while|as|from|in\s+the)\b", right, maxsplit=1, flags=re.IGNORECASE)[0].strip()
                subj = ManuscriptIngester._resolve_token(left, agent_map)
                obj = ManuscriptIngester._resolve_token(right, {**item_map, **agent_map})
                if subj and obj:
                    return {
                        "subject": subj,
                        "predicate": canonical_pred,
                        "object": obj,
                        "is_secret": is_secret,
                    }
        return None

    def parse_script_lines(
        self,
        script_text: str,
        *,
        use_llm: bool = False,
        llm_provider: LLMProvider | None = None,
    ) -> list[dict[str, Any]]:
        """Parse a manuscript containing `@tick` DSL lines, Fountain screenplay blocks,
        or natural-language Markdown prose into canonical event dictionaries.
        """
        provider = llm_provider or (self.llm_provider if use_llm else None)
        if use_llm and provider is not None:
            llm_events = self._parse_with_llm(script_text, provider)
            if llm_events:
                return llm_events

        agent_map, item_map, loc_map = self._build_lookup_maps()
        parsed: list[dict[str, Any]] = []
        auto_tick = 1
        current_time_mins = 60
        current_chapter = "Ch1"
        current_location = "study"

        lines = script_text.splitlines()
        idx = 0
        while idx < len(lines):
            raw_line = lines[idx]
            line = raw_line.strip()
            idx += 1

            if not line or line.startswith("//"):
                continue

            # 1. Explicit `@tick` Story-DSL line
            if line.startswith("@tick"):
                ev_dict = self._parse_at_tick_line(line, auto_tick)
                if ev_dict is not None:
                    parsed.append(ev_dict)
                    auto_tick = int(ev_dict["tick"]) + 1
                    current_time_mins = int(ev_dict["story_time_minutes"]) + 10
                    current_chapter = str(ev_dict["chapter_ref"])
                    current_location = str(ev_dict["location_id"])
                continue

            # 2. Markdown Chapter / Scene Heading or Fountain `INT.` / `EXT.` slugline
            heading_match = re.match(
                r"^(?:#+\s*(?:(Ch(?:apter)?\s*\d+)[:\s\-—]*)?|(?:INT\.|EXT\.|INT/EXT\.)\s*)(.+)$",
                line,
                flags=re.IGNORECASE,
            )
            if heading_match and not line.startswith("# "):
                ch_token = heading_match.group(1)
                rest = heading_match.group(2).strip()
                if ch_token:
                    current_chapter = re.sub(r"chapter\s*", "Ch", ch_token, flags=re.IGNORECASE).replace(" ", "")
                # Check for time in parentheses or after hyphen: `(Day 1, 09:00)` or `- DAY 1, 09:00`
                time_match = re.search(r"(Day\s*\d+\s*,\s*\d{1,2}:\d{2}|\d{1,2}:\d{2})", rest, flags=re.IGNORECASE)
                if time_match:
                    current_time_mins = parse_story_time_to_minutes(time_match.group(1), auto_tick)
                    rest_loc = rest[: time_match.start()].strip(" -—()[],")
                else:
                    rest_loc = re.split(r"[\-—(]", rest)[0].strip()
                if rest_loc:
                    current_location = self._resolve_token(rest_loc, loc_map)
                continue

            if line.startswith("#"):
                continue

            # 3. Multi-line Fountain Dialogue Block: `VANCE` followed by optional `(lying to Clara)` and speech line
            if (
                line.isupper()
                and 2 <= len(line) <= 32
                and not any( p in line for p in (":", ".", "|") )
                and idx < len(lines)
            ):
                speaker_id = self._resolve_token(line, agent_map)
                paren = ""
                if idx < len(lines) and lines[idx].strip().startswith("(") and lines[idx].strip().endswith(")"):
                    paren = lines[idx].strip()[1:-1].strip()
                    idx += 1
                speech_lines: list[str] = []
                while idx < len(lines) and lines[idx].strip():
                    speech_lines.append(lines[idx].strip())
                    idx += 1
                speech_text = " ".join(speech_lines)
                if speech_text:
                    ev_dict = self._build_dialogue_event(
                        tick=auto_tick,
                        story_time_minutes=current_time_mins,
                        chapter_ref=current_chapter,
                        location_id=current_location,
                        speaker_id=speaker_id,
                        parenthetical=paren,
                        speech_text=speech_text,
                        agent_map=agent_map,
                        item_map=item_map,
                    )
                    parsed.append(ev_dict)
                    auto_tick += 1
                    current_time_mins += 10
                continue

            # 4. Inline Speaker Dialogue: `VANCE (lying to Clara): Northern Rebels stole the Royal Peace Treaty!`
            inline_diag = re.match(
                r"^([A-Za-z][A-Za-z0-9_\s]{1,28}?)(?:\s*\(([^)]+)\))?\s*:\s*[\"']?(.+?)[\"']?$",
                line,
            )
            if inline_diag:
                speaker_raw, paren_raw, speech_raw = inline_diag.groups()
                if speaker_raw.strip().lower() in agent_map or speaker_raw.strip().isupper():
                    speaker_id = self._resolve_token(speaker_raw, agent_map)
                    ev_dict = self._build_dialogue_event(
                        tick=auto_tick,
                        story_time_minutes=current_time_mins,
                        chapter_ref=current_chapter,
                        location_id=current_location,
                        speaker_id=speaker_id,
                        parenthetical=paren_raw or "",
                        speech_text=speech_raw,
                        agent_map=agent_map,
                        item_map=item_map,
                    )
                    parsed.append(ev_dict)
                    auto_tick += 1
                    current_time_mins += 10
                    continue

            # 5. Natural-Language Prose Sentences inside a paragraph
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", line) if s.strip()]
            for sent in sentences:
                time_adv = re.search(r"(\d+)\s*(minutes?|hours?)\s+later", sent, flags=re.IGNORECASE)
                if time_adv:
                    val = int(time_adv.group(1))
                    unit = time_adv.group(2).lower()
                    current_time_mins += val * 60 if unit.startswith("hour") else val

                abs_time = re.search(r"(Day\s*\d+\s*,\s*\d{1,2}:\d{2})", sent, flags=re.IGNORECASE)
                if abs_time:
                    current_time_mins = parse_story_time_to_minutes(abs_time.group(1), auto_tick)

                prose_ev, new_loc = self._parse_natural_prose_sentence(
                    sentence=sent,
                    tick=auto_tick,
                    story_time_minutes=current_time_mins,
                    chapter_ref=current_chapter,
                    location_id=current_location,
                    agent_map=agent_map,
                    item_map=item_map,
                    loc_map=loc_map,
                )
                current_location = new_loc
                if prose_ev is not None:
                    parsed.append(prose_ev)
                    auto_tick += 1
                    current_time_mins += 10

        return parsed

    def _parse_at_tick_line(self, line: str, auto_tick: int) -> dict[str, Any] | None:
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 6:
            return None
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
        return {
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

    def _build_dialogue_event(
        self,
        *,
        tick: int,
        story_time_minutes: int,
        chapter_ref: str,
        location_id: str,
        speaker_id: str,
        parenthetical: str,
        speech_text: str,
        agent_map: dict[str, str],
        item_map: dict[str, str],
    ) -> dict[str, Any]:
        p_low = parenthetical.lower()
        is_lie = "lying" in p_low or "lies" in p_low or "deceiv" in p_low
        is_whisper = "whisper" in p_low or "aside" in p_low or "quiet" in p_low
        targets: list[str] = []
        to_match = re.search(r"\bto\s+([A-Za-z0-9_\s]+)", parenthetical, flags=re.IGNORECASE)
        if to_match:
            targets.append(self._resolve_token(to_match.group(1), agent_map))

        claim = self._extract_claim_from_clause(speech_text, agent_map, item_map, is_secret=is_whisper and not is_lie)
        claims = [claim] if claim is not None else []
        return {
            "tick": tick,
            "story_time_minutes": story_time_minutes,
            "chapter_ref": chapter_ref,
            "location_id": location_id,
            "actor_id": speaker_id,
            "event_type": "LIE" if is_lie else "TELL",
            "target_ids": targets,
            "visibility": "WHISPER" if (is_whisper or is_lie) else "PUBLIC_HERE",
            "item_id": None,
            "claims": claims,
            "summary": f"{speaker_id} {'lies' if is_lie else 'says'}: {speech_text}",
            "raw_text": speech_text,
        }

    def _parse_natural_prose_sentence(
        self,
        *,
        sentence: str,
        tick: int,
        story_time_minutes: int,
        chapter_ref: str,
        location_id: str,
        agent_map: dict[str, str],
        item_map: dict[str, str],
        loc_map: dict[str, str],
    ) -> tuple[dict[str, Any] | None, str]:
        s_clean = sentence.strip().strip("[]")
        cur_loc = location_id

        # Check explicit location prefix: "In the Royal Study, ..." or "At the Citadel Courtyard, ..."
        loc_prefix = re.match(r"^(?:In|At|Inside)\s+(?:the\s+)?([^,]+),\s*(.+)$", s_clean, flags=re.IGNORECASE)
        if loc_prefix:
            cand_loc = loc_prefix.group(1).strip()
            if cand_loc.lower() in loc_map:
                cur_loc = loc_map[cand_loc.lower()]
                s_clean = loc_prefix.group(2).strip()

        # Pattern A: LIE / TELL ("X lied to Y that <claim>" / "X told Y that <claim>" / "X whispered to Y that <claim>")
        comm_match = re.search(
            r"^(.+?)\s+(lied|lies|told|tells|whispered|whispers|reported|said|informed|warned)\s+(?:to\s+)?(.+?)\s+that\s+(.+)$",
            s_clean,
            flags=re.IGNORECASE,
        )
        if comm_match:
            actor_raw, verb_raw, target_raw, claim_raw = comm_match.groups()
            actor_id = self._resolve_token(actor_raw, agent_map)
            target_id = self._resolve_token(target_raw, agent_map)
            v_low = verb_raw.lower()
            is_lie = v_low.startswith("lie")
            is_whisper = v_low.startswith("whisper") or is_lie
            claim = self._extract_claim_from_clause(claim_raw, agent_map, item_map, is_secret=False)
            return (
                {
                    "tick": tick,
                    "story_time_minutes": story_time_minutes,
                    "chapter_ref": chapter_ref,
                    "location_id": cur_loc,
                    "actor_id": actor_id,
                    "event_type": "LIE" if is_lie else "TELL",
                    "target_ids": [target_id],
                    "visibility": "WHISPER" if is_whisper else "PUBLIC_HERE",
                    "item_id": None,
                    "claims": [claim] if claim else [],
                    "summary": s_clean,
                    "raw_text": s_clean,
                },
                cur_loc,
            )

        # Pattern B: GIVE_ITEM ("X gave/slipped/handed <item> to Y")
        give_match = re.search(
            r"^(.+?)\s+(?:secretly\s+)?(?:gave|gives|slipped|slips|handed|hands|passed|passes)\s+(.+?)\s+to\s+([A-Za-z0-9_\s]+?)(?:\.|,|$)",
            s_clean,
            flags=re.IGNORECASE,
        )
        if give_match:
            actor_raw, item_raw, target_raw = give_match.groups()
            actor_id = self._resolve_token(actor_raw, agent_map)
            item_id = self._resolve_token(item_raw, item_map)
            target_id = self._resolve_token(target_raw, agent_map)
            return (
                {
                    "tick": tick,
                    "story_time_minutes": story_time_minutes,
                    "chapter_ref": chapter_ref,
                    "location_id": cur_loc,
                    "actor_id": actor_id,
                    "event_type": "GIVE_ITEM",
                    "target_ids": [target_id],
                    "visibility": "WHISPER" if "secret" in s_clean.lower() or "slipped" in s_clean.lower() else "PUBLIC_HERE",
                    "item_id": item_id,
                    "claims": [{"subject": target_id, "predicate": "holds", "object": item_id, "is_secret": True}],
                    "summary": s_clean,
                    "raw_text": s_clean,
                },
                cur_loc,
            )

        # Pattern C: TAKE / USE / DROP ITEM ("X took/used/dropped/wielded <item>")
        item_act_match = re.search(
            r"^(.+?)\s+(took|takes|picked up|used|uses|wielded|wields|brandished|dropped|drops)\s+(.+?)(?:\s+in\s+the\s+([^.,]+))?[.,!]?$",
            s_clean,
            flags=re.IGNORECASE,
        )
        if item_act_match:
            actor_raw, verb_raw, item_raw, opt_loc = item_act_match.groups()
            cand_item = self._resolve_token(item_raw, item_map)
            if cand_item in item_map.values() or "_" in cand_item:
                if opt_loc and opt_loc.strip().lower() in loc_map:
                    cur_loc = loc_map[opt_loc.strip().lower()]
                actor_id = self._resolve_token(actor_raw, agent_map)
                v_low = verb_raw.lower()
                if v_low in ("took", "takes", "picked up"):
                    ev_type = "TAKE_ITEM"
                elif v_low in ("dropped", "drops"):
                    ev_type = "DROP_ITEM"
                else:
                    ev_type = "USE_ITEM"
                return (
                    {
                        "tick": tick,
                        "story_time_minutes": story_time_minutes,
                        "chapter_ref": chapter_ref,
                        "location_id": cur_loc,
                        "actor_id": actor_id,
                        "event_type": ev_type,
                        "target_ids": [],
                        "visibility": "PUBLIC_HERE",
                        "item_id": cand_item,
                        "claims": [],
                        "summary": s_clean,
                        "raw_text": s_clean,
                    },
                    cur_loc,
                )

        # Pattern D: MOVE ("X walked/moved/traveled/went to <location>")
        move_match = re.search(
            r"^(.+?)\s+(?:walked|walks|moved|moves|traveled|travels|went|ran|rushed)\s+to\s+(?:the\s+)?([^.,!]+)[.,!]?$",
            s_clean,
            flags=re.IGNORECASE,
        )
        if move_match:
            actor_raw, dest_raw = move_match.groups()
            actor_id = self._resolve_token(actor_raw, agent_map)
            dest_loc = self._resolve_token(dest_raw, loc_map)
            cur_loc = dest_loc
            return (
                {
                    "tick": tick,
                    "story_time_minutes": story_time_minutes,
                    "chapter_ref": chapter_ref,
                    "location_id": cur_loc,
                    "actor_id": actor_id,
                    "event_type": "MOVE",
                    "target_ids": [],
                    "visibility": "PUBLIC_HERE",
                    "item_id": None,
                    "claims": [],
                    "summary": s_clean,
                    "raw_text": s_clean,
                },
                cur_loc,
            )

        # Pattern E: DEATH ("X killed/murdered Y" or "X died")
        kill_match = re.search(
            r"^(.+?)\s+(?:killed|murdered|assassinated|stabbed)\s+([A-Za-z0-9_\s]+?)(?:\.|,|$)",
            s_clean,
            flags=re.IGNORECASE,
        )
        if kill_match:
            actor_raw, victim_raw = kill_match.groups()
            actor_id = self._resolve_token(actor_raw, agent_map)
            victim_id = self._resolve_token(victim_raw, agent_map)
            return (
                {
                    "tick": tick,
                    "story_time_minutes": story_time_minutes,
                    "chapter_ref": chapter_ref,
                    "location_id": cur_loc,
                    "actor_id": actor_id,
                    "event_type": "DEATH",
                    "target_ids": [victim_id],
                    "visibility": "STEALTH" if "secret" in s_clean.lower() else "PUBLIC_HERE",
                    "item_id": None,
                    "claims": [{"subject": actor_id, "predicate": "killed", "object": victim_id, "is_secret": "secret" in s_clean.lower()}],
                    "summary": s_clean,
                    "raw_text": s_clean,
                },
                cur_loc,
            )

        # Pattern F: General Witnessed / Secret Action ("Vance secretly burned the Royal Peace Treaty while Kael watched")
        is_secret = bool(re.search(r"\b(secretly|unseen|hidden|stealthily|in secret)\b", s_clean, flags=re.IGNORECASE))
        witness_targets: list[str] = []
        watch_match = re.search(
            r"\b(?:while|as)\s+([A-Za-z0-9_\s]+?)\s+(?:watched|witnessed|saw|overheard|eavesdropped|observed)",
            s_clean,
            flags=re.IGNORECASE,
        )
        if watch_match:
            witness_targets.append(self._resolve_token(watch_match.group(1), agent_map))

        claim = self._extract_claim_from_clause(s_clean, agent_map, item_map, is_secret=is_secret)
        if claim is not None:
            return (
                {
                    "tick": tick,
                    "story_time_minutes": story_time_minutes,
                    "chapter_ref": chapter_ref,
                    "location_id": cur_loc,
                    "actor_id": claim["subject"],
                    "event_type": "WITNESS_ACTION",
                    "target_ids": witness_targets,
                    "visibility": "STEALTH" if is_secret else "PUBLIC_HERE",
                    "item_id": claim["object"] if claim["object"] in item_map.values() else None,
                    "claims": [claim],
                    "summary": s_clean,
                    "raw_text": s_clean,
                },
                cur_loc,
            )

        return None, cur_loc

    def _parse_with_llm(self, script_text: str, provider: LLMProvider) -> list[dict[str, Any]]:
        """Extract canonical event dictionaries from freeform prose via an LLMProvider in JSON mode."""
        sys_prompt = (
            "You are the LoreSim Narrative Event Compiler. Extract chronological world events from the user's prose.\n"
            "Return a JSON object with key 'events' containing a list of event objects, each with fields:\n"
            "  tick (int), story_time_minutes (int), chapter_ref (str), location_id (str), actor_id (str),\n"
            "  event_type ('WITNESS_ACTION'|'TELL'|'LIE'|'MOVE'|'GIVE_ITEM'|'TAKE_ITEM'|'USE_ITEM'|'DROP_ITEM'|'DEATH'),\n"
            "  target_ids (list[str]), visibility ('PUBLIC_HERE'|'WHISPER'|'STEALTH'), item_id (str|null),\n"
            "  claims (list[{'subject': str, 'predicate': str, 'object': str, 'is_secret': bool}]),\n"
            "  summary (str), raw_text (str)."
        )
        try:
            raw_json = provider.complete(sys_prompt, script_text, temperature=0.0, json_mode=True)
            data = json.loads(raw_json)
            events = data.get("events", data) if isinstance(data, dict) else data
            if isinstance(events, list) and all(isinstance(x, dict) for x in events):
                return events
        except Exception:
            pass
        return []
