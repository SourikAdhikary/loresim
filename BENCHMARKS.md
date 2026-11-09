# LoreSim Reproducible A/B Benchmarks (`Without LoreSim` vs. `With LoreSim`)

- **Runtime Environment:** `macOS-26.6.2-arm64-arm-64bit-Mach-O` | Python `3.13.7` | Native Rust Kernel (`libloresim_core`): `True` (v`200`)
- **Reproduce Command:** `make bench` (`PYTHONPATH=src:. python -m benchmarks.runner`)

## 1. Systems, Epistemic, Simulation & Studio UI Benchmarks (`B1`–`B6`)

| Suite | Metric | Without LoreSim (Baseline) | With LoreSim (`Rust + Python Kernel`) | Improvement |
| :--- | :--- | :--- | :--- | :--- |
| **B1** | 60-Turn Omniscient Secret Leak Rate | `100.0%` (Flat RAG) | **`0.0%`** (`EpistemicPromptFirewall`) | **`-100.0%` secret leakage** |
| **B1** | False-Belief Roleplay Fidelity & Prompt Tokens | `0.0%` (`5,750` tok) | **`100.0%`** (`3,186` tok) | **`-44.6%` prompt tokens** |
| **B2** | 30-Chapter Plot-Hole Recall (`35` injected bugs, `LINT-01..07`) | `14.3%` (Surface check) | **`100.0%`** (`3.88 ms` total) | **`+85.7%` plot-hole recall** |
| **B3** | 16-Agent Rumor/Lie Contagion & Firsthand Lie Exposure | `25.0%` / `0.0%` | **`100.0%` / `100.0%`** | **`100%` exact contagion & lie detection** |
| **B4** | 100-Tick Living World + 60 FPS 2D Stage Latency | `850.0 ms/tick` (`Smallville`-style) | **`2.346 ms/tick`** (`$0.00` visual cost) | **`362.3x` faster / `-99.7%` tokens** |
| **B5** | Butterfly-Effect Blast-Radius Recall & 30-Branch Forking | `0.0%` automated (`Manual re-read`) | **`100.0%`** in **`0.212 ms`** (`0.175 ms` fork) | **`0.0%` cross-branch contamination** |
| **B6** | Live 60 FPS Studio UI Run (`5` Ticks, `25` Mind X-Rays, Interrogate + Butterfly) | `~12,000 ms/frame` (`~$0.40/scene` gen-video) | **`0.75 ms/frame`** (`$0.00` Canvas + WebSpeech) | **`22.2x` faster than 60 FPS budget** |

## 2. Narrative Trap Gauntlets (`S1`–`S4`)

| Trap ID | Scenario | Result | Verification Detail |
| :--- | :--- | :--- | :--- |
| **S1** | Murderer's Tell (Omniscient Leak Trap) | **PASS** | `{"sandboxed_leaks": 0, "forced_leak_trapped": true}` |
| **S2** | Double-Cross Lie Exposure & Composure Collapse | **PASS** | `{"kael_trust_after_lie": -0.1, "suspect_final_composure": 0.0, "suspect_cracked": true}` |
| **S3** | Fast-Travel & Ghost Dagger Trap (LINT-02 + LINT-03) | **PASS** | `{"caught_rules": ["LINT-02", "LINT-03"]}` |
| **S4** | Forgotten Prophecy Chekhov Thread Trap (LINT-06) | **PASS** | `{"dangling_threads_caught": 1}` |
