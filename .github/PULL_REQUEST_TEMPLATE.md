## Summary
- Describe the change and which architectural layer (`crates/loresim-core`, `core`, `storage`, `world`, `epistemic`, `compiler`, `simulator`, `interfaces`) it touches.

## Verification Checklist
- [ ] `make build-rust` passes (`cargo build --release && cargo test --release`)
- [ ] `make check` passes (`ruff check`)
- [ ] `make test` passes (including `test_layer_boundaries.py` and `test_ab_gates.py`)
- [ ] `make doctor` passes (`12/12` formal invariants)
