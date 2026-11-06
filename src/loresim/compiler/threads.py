"""Chekhov's Gun / Dangling Narrative Thread tracker (LINT-06)."""

from __future__ import annotations

import uuid

from loresim.core.types import NarrativeThread
from loresim.storage.db import SQLiteDatabase


class ChekhovThreadTracker:
    """Tracks narrative setups, mysteries, and prophecies to flag dormant threads."""

    def __init__(self, db: SQLiteDatabase, stale_threshold_ticks: int = 12) -> None:
        self.db = db
        self.stale_threshold_ticks = stale_threshold_ticks

    def introduce_thread(
        self,
        title: str,
        category: str = "Mystery",
        introduced_tick: int = 1,
        payoff_notes: str = "",
        branch_ref: str = "main",
        thread_id: str | None = None,
    ) -> NarrativeThread:
        branch_id = self.db.resolve_branch_id(branch_ref)
        tid = thread_id or f"thr_{uuid.uuid4().hex[:10]}"
        thread = NarrativeThread(
            thread_id=tid,
            branch_id=branch_id,
            title=title,
            category=category,
            introduced_tick=int(introduced_tick),
            last_touched_tick=int(introduced_tick),
            resolved_tick=None,
            status="OPEN",
            payoff_notes=payoff_notes,
        )
        with self.db.transaction():
            self.db.execute(
                """
                INSERT OR REPLACE INTO narrative_threads
                (thread_id, branch_id, title, category, introduced_tick, last_touched_tick,
                 resolved_tick, status, payoff_notes)
                VALUES (?, ?, ?, ?, ?, ?, NULL, 'OPEN', ?)
                """,
                (
                    thread.thread_id,
                    thread.branch_id,
                    thread.title,
                    thread.category,
                    thread.introduced_tick,
                    thread.last_touched_tick,
                    thread.payoff_notes,
                ),
            )
        return thread

    def touch_thread(self, thread_id: str, tick: int) -> None:
        self.db.execute(
            "UPDATE narrative_threads SET last_touched_tick = MAX(last_touched_tick, ?) WHERE thread_id = ?",
            (int(tick), thread_id),
        )

    def resolve_thread(self, thread_id: str, tick: int, payoff_notes: str = "") -> None:
        self.db.execute(
            """
            UPDATE narrative_threads
            SET last_touched_tick = MAX(last_touched_tick, ?),
                resolved_tick = ?,
                status = 'RESOLVED',
                payoff_notes = CASE WHEN ? != '' THEN ? ELSE payoff_notes END
            WHERE thread_id = ?
            """,
            (int(tick), int(tick), payoff_notes, payoff_notes, thread_id),
        )

    def list_threads(self, branch_ref: str = "main") -> list[NarrativeThread]:
        branch_id = self.db.resolve_branch_id(branch_ref)
        rows = self.db.fetchall(
            "SELECT * FROM narrative_threads WHERE branch_id = ? ORDER BY introduced_tick ASC",
            (branch_id,),
        )
        return [
            NarrativeThread(
                thread_id=str(r["thread_id"]),
                branch_id=str(r["branch_id"]),
                title=str(r["title"]),
                category=str(r["category"]),
                introduced_tick=int(r["introduced_tick"]),
                last_touched_tick=int(r["last_touched_tick"]),
                resolved_tick=r["resolved_tick"],
                status=str(r["status"]),
                payoff_notes=str(r["payoff_notes"]),
            )
            for r in rows
        ]

    def find_dangling_threads(
        self,
        branch_ref: str = "main",
        current_tick: int | None = None,
        threshold_ticks: int | None = None,
    ) -> list[NarrativeThread]:
        head = current_tick if current_tick is not None else self.db.get_branch_head_tick(branch_ref)
        thresh = threshold_ticks if threshold_ticks is not None else self.stale_threshold_ticks
        dangling: list[NarrativeThread] = []
        for t in self.list_threads(branch_ref=branch_ref):
            if t.status == "OPEN" and (head - t.last_touched_tick) >= thresh:
                dangling.append(t)
        return dangling
