PYTHON ?= /Users/sourik/Projects/.venv/bin/python
PYTEST ?= /Users/sourik/Projects/.venv/bin/pytest
RUFF ?= /Users/sourik/Projects/vide-proposal/.venv/bin/ruff
CARGO ?= /Users/sourik/.cargo/bin/cargo

.PHONY: all build-rust check test test-unit test-chaos test-integration test-bench doctor bench studio clean

all: build-rust check test doctor bench

build-rust:
	$(CARGO) build --release
	$(CARGO) test --release

check:
	$(RUFF) check src benchmarks tests

test: build-rust
	PYTHONPATH=src:. $(PYTEST) tests/

test-unit:
	PYTHONPATH=src:. $(PYTEST) tests/unit/

test-chaos:
	PYTHONPATH=src:. $(PYTEST) tests/chaos/

test-integration:
	PYTHONPATH=src:. $(PYTEST) tests/integration/

test-bench:
	PYTHONPATH=src:. $(PYTEST) tests/benchmarks/

doctor: build-rust
	PYTHONPATH=src:. $(PYTHON) -m loresim.interfaces.cli doctor

bench: build-rust
	PYTHONPATH=src:. $(PYTHON) -m benchmarks.runner

studio: build-rust
	PYTHONPATH=src:. $(PYTHON) -m loresim.interfaces.cli studio --port 8420

clean:
	rm -rf .loresim .pytest_cache .ruff_cache build dist src/*.egg-info
	find . -name "__pycache__" -type d -exec rm -rf {} +
