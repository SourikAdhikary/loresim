"""Linear-type unique item conservation ledger across narrative ticks and branches."""

from __future__ import annotations

import json
import uuid

from loresim.core.types import ItemEntity
from loresim.storage.db import SQLiteDatabase


class InventoryTracker:
    """Enforces single-holder linear conservation for unique items at any `(branch, tick)`."""

    def __init__(self, db: SQLiteDatabase) -> None:
        self.db = db

    def register_item(
        self,
        item_id: str,
        name: str,
        is_unique: bool = True,
        description: str = "",
        icon: str = "🗡️",
        initial_holder_id: str | None = None,
        initial_holder_type: str = "AGENT",
        branch_ref: str = "main",
        tick: int = 0,
    ) -> ItemEntity:
        props = json.dumps({"icon": icon})
        item = ItemEntity(
            item_id=item_id,
            name=name,
            is_unique=is_unique,
            description=description,
            icon=icon,
        )
        with self.db.transaction():
            self.db.execute(
                """
                INSERT OR REPLACE INTO items (item_id, name, is_unique, description, properties_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (item.item_id, item.name, 1 if item.is_unique else 0, item.description, props),
            )
            if initial_holder_id is not None:
                self.record_transfer(
                    item_id=item_id,
                    to_holder_id=initial_holder_id,
                    to_holder_type=initial_holder_type,
                    tick=tick,
                    event_id="init_transfer",
                    branch_ref=branch_ref,
                )
        return item

    def get_item(self, item_id: str) -> ItemEntity | None:
        row = self.db.fetchone("SELECT * FROM items WHERE item_id = ?", (item_id,))
        if row is None:
            return None
        props = json.loads(str(row["properties_json"] or "{}"))
        return ItemEntity(
            item_id=str(row["item_id"]),
            name=str(row["name"]),
            is_unique=bool(row["is_unique"]),
            description=str(row["description"]),
            icon=str(props.get("icon", "🗡️")),
        )

    def record_transfer(
        self,
        item_id: str,
        to_holder_id: str,
        to_holder_type: str = "AGENT",
        tick: int = 0,
        event_id: str = "",
        branch_ref: str = "main",
    ) -> None:
        branch_id = self.db.resolve_branch_id(branch_ref)
        entry_id = f"iled_{uuid.uuid4().hex[:12]}"
        self.db.execute(
            """
            INSERT INTO item_ledger (entry_id, branch_id, tick, item_id, holder_type, holder_id, event_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (entry_id, branch_id, int(tick), item_id, to_holder_type, to_holder_id, event_id),
        )

    def get_current_holder(
        self, item_id: str, branch_ref: str = "main", query_tick: int | None = None
    ) -> tuple[str, str, int, str] | None:
        """Return `(holder_type, holder_id, tick, event_id)` for `item_id` at `(branch_ref, query_tick)`."""
        bounds = self.db.get_branch_ancestry_bounds(branch_ref, query_tick)
        best: tuple[str, str, int, str] | None = None
        for b_id, cap_tick in bounds:
            row = self.db.fetchone(
                """
                SELECT holder_type, holder_id, tick, event_id
                FROM item_ledger
                WHERE branch_id = ? AND item_id = ? AND tick <= ?
                ORDER BY tick DESC, rowid DESC
                LIMIT 1
                """,
                (b_id, item_id, cap_tick),
            )
            if row is not None:
                best = (
                    str(row["holder_type"]),
                    str(row["holder_id"]),
                    int(row["tick"]),
                    str(row["event_id"]),
                )
        return best

    def get_agent_held_items(
        self, agent_id: str, branch_ref: str = "main", query_tick: int | None = None
    ) -> list[ItemEntity]:
        rows = self.db.fetchall("SELECT item_id FROM items ORDER BY item_id")
        held: list[ItemEntity] = []
        for r in rows:
            iid = str(r["item_id"])
            holder = self.get_current_holder(iid, branch_ref=branch_ref, query_tick=query_tick)
            if holder is not None and holder[0] == "AGENT" and holder[1] == agent_id:
                item = self.get_item(iid)
                if item is not None:
                    held.append(item)
        return held
