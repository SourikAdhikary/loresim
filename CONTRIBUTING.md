# Contributing to LoreSim

Thank you for contributing to **LoreSim** (`Rust Core + Python Epistemic World, Continuity Compiler & 60 FPS 2D NPC Theater Engine`).

## Strict 6-Layer DAG Architecture

`LoreSim` enforces a strict one-way dependency graph across `src/loresim/` (verified by `tests/unit/test_layer_boundaries.py`):

1. **Layer 0 (`core`):** `config.py`, `clock.py`, `errors.py`, `hashing.py`, `rust_bridge.py`, `types.py` (Zero imports from Layers 1–5; bridges to `crates/loresim-core`).
2. **Layer 1 (`storage`):** `schema.py`, `db.py` (May only import from `core`).
3. **Layer 2 (`world`):** `spatial.py`, `inventory.py`, `agents.py` (May only import from `core`, `storage`).
4. **Layer 3 (`epistemic`):** `vault.py`, `propagator.py`, `firewall.py`, `irony.py` (May only import from `core`, `storage`, `world`).
5. **Layer 4 (`compiler` & `simulator`):** `linter.py`, `butterfly.py`, `threads.py`, `ingester.py`, `stage_director.py`, `scene.py`, `doctor.py` (May only import from Layers 0–3).
6. **Layer 5 (`interfaces`):** `engine.py`, `cli.py`, `mcp_server.py`, `studio.py` (Top-level user & SDK entrypoints).

## Development Workflow

```bash
make build-rust   # Compile crates/loresim-core (--release) and run cargo tests
make check        # Run ruff lint checks
make test         # Run unit, chaos, integration, and A/B benchmark regression gates
make doctor       # Verify all 12 formal mathematical & relational kernel invariants
make bench        # Run all 9 A/B benchmarks and update BENCHMARKS.md
```
