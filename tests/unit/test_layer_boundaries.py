"""AST Import Linter enforcing the strict 6-layer Directed Acyclic Graph (DAG) in `src/loresim/`."""

from __future__ import annotations

import ast
from pathlib import Path

LAYER_RANK = {
    "core": 0,
    "storage": 1,
    "world": 2,
    "epistemic": 3,
    "compiler": 4,
    "simulator": 4,
    "interfaces": 5,
}


def test_strict_six_layer_dag_boundaries() -> None:
    src_root = Path(__file__).resolve().parents[2] / "src" / "loresim"
    violations: list[str] = []

    for py_file in sorted(src_root.rglob("*.py")):
        rel = py_file.relative_to(src_root)
        if len(rel.parts) < 2:
            continue  # Top-level __init__.py
        src_layer = rel.parts[0]
        if src_layer not in LAYER_RANK:
            continue
        src_rank = LAYER_RANK[src_layer]

        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            imported_mod: str | None = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_mod = alias.name
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_mod = node.module

            if imported_mod and imported_mod.startswith("loresim."):
                parts = imported_mod.split(".")
                if len(parts) >= 2:
                    dst_layer = parts[1]
                    if dst_layer in LAYER_RANK:
                        dst_rank = LAYER_RANK[dst_layer]
                        if dst_rank > src_rank:
                            violations.append(
                                f"{rel} (Layer {src_rank}:{src_layer}) imports higher layer {imported_mod} (Layer {dst_rank}:{dst_layer})"
                            )

    assert not violations, "Layer DAG boundary violations:\n" + "\n".join(violations)
