"""Configuration and runtime path management for LoreSim."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LoreSimConfig:
    """Immutable configuration for a LoreSim workspace."""

    workspace_root: Path
    world_name: str = "DefaultWorld"
    calendar_epoch: str = "Day 1, 00:00"
    stale_thread_tick_threshold: int = 12
    composure_crack_threshold: float = 25.0
    strict_mode: bool = False

    @property
    def loresim_dir(self) -> Path:
        return self.workspace_root / ".loresim"

    @property
    def db_path(self) -> Path:
        return self.loresim_dir / "world.db"

    def ensure_dirs(self) -> None:
        self.loresim_dir.mkdir(parents=True, exist_ok=True)
