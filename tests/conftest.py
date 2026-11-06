"""Shared pytest fixtures for LoreSim."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from loresim.interfaces.engine import LoreSimEngine


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[LoreSimEngine]:
    eng = LoreSimEngine(tmp_path / "ws")
    try:
        yield eng
    finally:
        eng.close()
