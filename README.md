# 🎭 LoreSim: Epistemic World, Narrative Continuity & 60 FPS 2D NPC Theater Engine

**`LoreSim`** is a hybrid **Rust (`crates/loresim-core`) + Python (`src/loresim`)** engine that brings **Dynamic Epistemic Logic ($\text{KD45}_n$)**, **Bi-Temporal World State**, **7-Rule Plot-Hole Compilation**, **Butterfly-Effect Causal Blast-Radius Tracing**, and a **Zero-Cost 60 FPS 2D NPC Stage Studio** to interactive narratives, living game NPCs, novels, and Tabletop RPG campaigns.

---

## Why `LoreSim` Exists

Existing tools for stories, game NPCs, and multi-agent worlds fail in three ways:
1. **Static Wikis (`WorldAnvil`, `Campfire`, `Notion`):** Dead text forms with zero state machine, zero plot-hole detection, and zero ability to watch characters interact.
2. **Naive LLM Chat / Vector RAG (`ChatGPT`, `Sudowrite`, Standard Vector DBs):** Suffer from the **"Omniscient Hive-Mind Leak"**—if Character A hides a dagger in Chapter 2, Character B (300 miles away) magically acts suspicious of the dagger in Chapter 10 because all facts sit in one shared vector index.
3. **Academic Agent Loops (Stanford `Smallville`):** Burn `$30–$50/hr` in tokens by using LLM reflection calls for basic spatial/witness physics and cannot distinguish objective truth from lies or secrets.

`LoreSim` solves this by strictly separating **Objective Canonical Reality ($\mathcal{W}_t$)** from **Subjective Per-Character Epistemic Vaults ($\mathcal{B}_a(t)$)** inside a single-file bi-temporal SQLite WAL database accelerated by a native **Rust kernel (`libloresim_core`)**.

---

## 5 Killer Capabilities

1. **🎭 Zero-Cost 60 FPS 2D NPC Theater (`loresim studio`):**
   Watch procedural 2D NPC puppets walk across rooms, huddle inside expanding **acoustic earshot rings**, pass items along **parabolic trajectories**, sweat when lying (`😰💧`), and react with **`😱❗`** shock badges when caught in a contradiction—rendered at 60 FPS in HTML5 Canvas at **`$0.00` image/video API cost**, with built-in multi-voice speech synthesis.
2. **🛡️ Zero-Leak Epistemic Prompt Firewall (`EpistemicPromptFirewall`):**
   Compiles each NPC's prompt strictly from their private $\mathcal{B}_a(b, t)$ vault (`FIRSTHAND`, `HEARSAY`, `EAVESDROP`, `DECEIVED`, `WITHHOLDS_SECRET`), guaranteeing **`0.0%` omniscient secret leakage**.
3. **🔍 7-Rule Continuity & Plot-Hole Compiler (`loresim lint`):**
   Detects **Epistemic Secret Leaks (`LINT-01`)**, **Spatial Teleportation (`LINT-02`)**, **Linear Inventory Violations (`LINT-03`)**, **Dead-Actor Actions (`LINT-04`)**, **Immutable Attribute Contradictions (`LINT-05`)**, **Dangling Chekhov Threads (`LINT-06`)**, and **Firsthand Lie Exposures (`LINT-07`)** in `<6 ms`.
4. **🦋 "Butterfly Effect" Causal Blast-Radius Tracer (`loresim butterfly`):**
   Disable or mutate any historical event in Chapter 1 and trace every downstream scene and belief across the story that becomes causally or epistemically impossible in **`<0.3 ms`**.
5. **🕵️ Live Detective Interrogation & Rumor Contagion Map (`loresim interrogate`):**
   Cross-examine any NPC at any tick $t$; presenting firsthand evidence that contradicts their cover story collapses their **Composure Meter** until they confess.

---

## Reproducible A/B Benchmarks (`Without LoreSim` vs. `With LoreSim`)

Run `make bench` to reproduce all 9 benchmarks (`B1`–`B5` + `S1`–`S4` in [`BENCHMARKS.md`](BENCHMARKS.md)):

| Suite | Metric | Without LoreSim (Baseline) | With LoreSim (`Rust + Python`) | Measured Improvement |
| :--- | :--- | :--- | :--- | :--- |
| **`B1`** | 60-Turn Omniscient Secret Leak Rate | `100.0%` (Flat RAG) | **`0.0%`** (`EpistemicPromptFirewall`) | **`-100.0%` secret leakage** |
| **`B1`** | False-Belief Roleplay Fidelity & Tokens | `0.0%` (`5,750` tok) | **`100.0%`** (`3,186` tok) | **`-44.6%` prompt tokens** |
| **`B2`** | 30-Chapter Plot-Hole Recall (`35` bugs, `LINT-01..07`) | `14.3%` (Surface check) | **`100.0%`** (`5.68 ms` total) | **`+85.7%` plot-hole recall** |
| **`B3`** | 16-Agent Rumor/Lie Contagion & Lie Exposure | `25.0%` / `0.0%` | **`100.0%` / `100.0%`** | **`100%` exact contagion & lie detection** |
| **`B4`** | 100-Tick Living World + 60 FPS 2D Stage Latency | `850.0 ms/tick` (`Smallville`-style) | **`2.394 ms/tick`** (`$0.00` visual cost) | **`355.1x` faster / `-99.7%` tokens** |
| **`B5`** | Butterfly-Effect Blast Radius & 30-Branch Forking | `0.0%` automated | **`100.0%`** in **`0.221 ms`** (`0.182 ms` fork) | **`0.0%` cross-branch contamination** |

---

## Quickstart

```bash
git clone https://github.com/SourikAdhikary/loresim.git
cd loresim

# 1. Build the native Rust kernel, run lint checks, unit/chaos/integration tests, and 12/12 doctor invariants
make build-rust
make check
make test
make doctor

# 2. Launch the 60 FPS 2D NPC Theater & Contagion Map Studio in your browser
make studio
# -> Open http://127.0.0.1:8420
```

## License

Apache-2.0 — see [LICENSE](LICENSE).
