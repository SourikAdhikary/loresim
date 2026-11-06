"""SQLite WAL connection manager, savepoint transactions, and bi-temporal branch ancestry."""

from __future__ import annotations

import sqlite3
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from loresim.core.config import LoreSimConfig
from loresim.core.errors import ParadoxError
from loresim.storage.schema import SCHEMA_SQL


class SQLiteDatabase:
    """Thread-safe SQLite WAL database engine with bi-temporal branch visibility helpers."""

    def __init__(self, config: LoreSimConfig) -> None:
        self.config = config
        self.config.ensure_dirs()
        self._conn = self._connect(self.config.db_path)
        self._init_schema()

    @staticmethod
    def _connect(db_path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA temp_store = MEMORY;")
        conn.execute("PRAGMA cache_size = -32000;")
        return conn

    def _init_schema(self) -> None:
        self._conn.executescript(SCHEMA_SQL)
        row = self.fetchone("SELECT world_id FROM worlds LIMIT 1")
        if row is None:
            now = time.time()
            world_id = "world_default"
            with self.transaction():
                self.execute(
                    "INSERT INTO worlds (world_id, name, calendar_epoch, created_at) VALUES (?, ?, ?, ?)",
                    (world_id, self.config.world_name, self.config.calendar_epoch, now),
                )
                self.execute(
                    """
                    INSERT INTO branches (branch_id, world_id, name, parent_branch_id, fork_tick, head_tick, created_at)
                    VALUES (?, ?, ?, NULL, 0, 0, ?)
                    """,
                    ("branch_main", world_id, "main", now),
                )

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        sp_name = f"sp_{uuid.uuid4().hex[:10]}"
        self._conn.execute(f"SAVEPOINT {sp_name}")
        try:
            yield self._conn
        except Exception:
            self._conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
            self._conn.execute(f"RELEASE SAVEPOINT {sp_name}")
            raise
        else:
            self._conn.execute(f"RELEASE SAVEPOINT {sp_name}")

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        return self._conn.execute(sql, params)

    def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        return self._conn.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        return self._conn.execute(sql, params).fetchall()

    def resolve_branch_id(self, branch_ref: str = "main") -> str:
        row = self.fetchone(
            "SELECT branch_id FROM branches WHERE name = ? OR branch_id = ?",
            (branch_ref, branch_ref),
        )
        if row is None:
            raise ParadoxError(f"Unknown narrative branch: {branch_ref}")
        return str(row["branch_id"])

    def get_branch_head_tick(self, branch_ref: str = "main") -> int:
        branch_id = self.resolve_branch_id(branch_ref)
        row = self.fetchone("SELECT head_tick FROM branches WHERE branch_id = ?", (branch_id,))
        return int(row["head_tick"]) if row else 0

    def advance_branch_head_tick(self, branch_id: str, tick: int) -> None:
        self.execute(
            "UPDATE branches SET head_tick = MAX(head_tick, ?) WHERE branch_id = ?",
            (int(tick), branch_id),
        )

    def fork_branch(self, new_name: str, from_branch: str = "main", fork_tick: int | None = None) -> str:
        """Create an O(1) counterfactual narrative branch at `fork_tick`."""
        parent_id = self.resolve_branch_id(from_branch)
        parent_row = self.fetchone(
            "SELECT world_id, head_tick, fork_tick FROM branches WHERE branch_id = ?",
            (parent_id,),
        )
        if parent_row is None:
            raise ParadoxError(f"Parent branch not found: {from_branch}")
        actual_fork_tick = int(parent_row["head_tick"]) if fork_tick is None else int(fork_tick)
        if actual_fork_tick < int(parent_row["fork_tick"]):
            raise ParadoxError(
                f"Cannot fork branch '{new_name}' at tick {actual_fork_tick} before parent fork_tick {parent_row['fork_tick']}"
            )
        new_id = f"branch_{uuid.uuid4().hex[:10]}"
        with self.transaction():
            self.execute(
                """
                INSERT INTO branches (branch_id, world_id, name, parent_branch_id, fork_tick, head_tick, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id,
                    str(parent_row["world_id"]),
                    new_name,
                    parent_id,
                    actual_fork_tick,
                    actual_fork_tick,
                    time.time(),
                ),
            )
        return new_id

    def get_branch_ancestry_bounds(self, branch_ref: str, query_tick: int | None = None) -> list[tuple[str, int]]:
        """Return ordered `[(branch_id, max_visible_tick), ...]` from root (`main`) to `branch_ref`.

        Ensures bi-temporal isolation: on a child branch forked at `fork_tick = 15`, events on `main`
        at `tick > 15` are strictly invisible!
        """
        branch_id = self.resolve_branch_id(branch_ref)
        head_tick = self.get_branch_head_tick(branch_id)
        max_t = head_tick if query_tick is None else int(query_tick)

        chain: list[tuple[str, str | None, int]] = []
        curr: str | None = branch_id
        visited: set[str] = set()
        while curr is not None:
            if curr in visited:
                raise ParadoxError(f"Cycle detected in narrative branch tree at {curr}")
            visited.add(curr)
            row = self.fetchone(
                "SELECT branch_id, parent_branch_id, fork_tick FROM branches WHERE branch_id = ?",
                (curr,),
            )
            if row is None:
                break
            chain.append((str(row["branch_id"]), row["parent_branch_id"], int(row["fork_tick"])))
            curr = row["parent_branch_id"]

        # `chain` is [leaf, parent, ..., root].
        # For each ancestor i (where i > 0), its visible events are capped at child's `fork_tick` (and `max_t`).
        bounds: list[tuple[str, int]] = []
        for idx, (b_id, _, _) in enumerate(chain):
            if idx == 0:
                cap = max_t
            else:
                child_fork_tick = chain[idx - 1][2]
                cap = min(max_t, child_fork_tick)
            bounds.append((b_id, cap))
        bounds.reverse()
        return bounds

    def build_bitemporal_sql_Clause(
        self, branch_ref: str, query_tick: int | None = None, table_alias: str = ""
    ) -> tuple[str, tuple[Any, ...]]:
        """Build a parameterized SQL WHERE clause enforcing bi-temporal `(branch_id, tick)` visibility."""
        prefix = f"{table_alias}." if table_alias else ""
        bounds = self.get_branch_ancestry_bounds(branch_ref, query_tick)
        clauses: list[str] = []
        params: list[Any] = []
        for b_id, cap_tick in bounds:
            clauses.append(f"({prefix}branch_id = ? AND {prefix}tick <= ?)")
            params.extend([b_id, cap_tick])
        sql = "(" + " OR ".join(clauses) + ")" if clauses else "(1 = 0)"
        return sql, tuple(params)

    def close(self) -> None:
        self._conn.close()
