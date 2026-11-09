# 🎭 LoreSim — Living Worlds & NPCs That Only Know What They’ve Seen or Heard

**Simulate stories, games, and RPG worlds where characters have their own private memories, secrets, and lies—catch plot holes automatically and watch NPCs act out scenes live on a 2D stage.**

---

## Why `LoreSim` Exists

When you build a story, a game with AI NPCs, or a D&D campaign, existing tools break as soon as things get complex:
1. **Static Wikis (`WorldAnvil`, `Notion`):** You have to update everything by hand, they can't catch plot holes, and characters are just dead text pages.
2. **Standard AI Chat (`ChatGPT`, `Claude`, Vector RAG):** Every character shares one giant brain. If Character A hides a dagger in Chapter 2 while Character B is 300 miles away, Character B magically knows about the dagger in Chapter 10.
3. **Slow Agent Sims (`Smallville`):** Cost $40+ an hour in API calls just to move characters around a map and still can't tell the difference between a secret, a rumor, and a lie.

**`LoreSim` fixes this.** It tracks **what actually happened in the world** separately from **what each character personally saw, heard, or was lied to about**—powered by a fast Rust + SQLite engine and a built-in 2D stage where you can watch your characters act out every scene.

---

## What You Can Do With `LoreSim`

1. **🎭 Watch NPCs Act Out Scenes Live (`loresim studio`):**
   Open a 60 FPS 2D stage in your browser where characters walk between rooms, lean in to whisper secrets, pass items to each other, sweat when lying, and react with shock when caught in a lie—at **$0 image/video API cost**.
2. ** Keep Secrets & Lies Strictly Separate:**
   Each character only knows what they witnessed firsthand or were told by someone else. If someone lies to them, they genuinely believe and repeat the lie until proven otherwise.
3. **🔍 Catch Plot Holes Automatically (`loresim lint`):**
   Scans your chapters, scripts, or campaign notes in milliseconds to catch **7 types of story bugs**:
   * A character mentioning a secret nobody told them yet
   * Traveling between two cities faster than physically possible
   * Using an item someone else is currently holding
   * A dead character speaking or acting later in the timeline
   * Contradicting a character's established traits (like eye color or background)
   * Forgotten plot threads ("Chekhov's guns") introduced early and never resolved
   * A character lying to someone who witnessed the truth firsthand
4. ** Test the "Butterfly Effect" (`loresim butterfly`):**
   Change or delete one event in Chapter 1 (*"What if Vance never burned the treaty?"*) and immediately see every future scene across the story that breaks as a result.
5. ** Interrogate Any Character (`loresim interrogate`):**
   Step into the story at any point on the timeline and question any character. Present evidence that contradicts a suspect's alibi to watch their composure crack until they confess.

---

## Reproducible A/B Benchmarks (`Without LoreSim` vs. `With LoreSim`)

Run `make bench` to reproduce all 10 benchmarks (`B1`–`B6` + `S1`–`S4` in [`BENCHMARKS.md`](BENCHMARKS.md)):

| Suite | Metric | Without LoreSim (Baseline) | With LoreSim (`Rust + Python`) | Measured Improvement |
| :--- | :--- | :--- | :--- | :--- |
| **`B1`** | 60-Turn Omniscient Secret Leak Rate | `100.0%` (Flat RAG) | **`0.0%`** (`EpistemicPromptFirewall`) | **`-100.0%` secret leakage** |
| **`B1`** | False-Belief Roleplay Fidelity & Tokens | `0.0%` (`5,750` tok) | **`100.0%`** (`3,186` tok) | **`-44.6%` prompt tokens** |
| **`B2`** | 30-Chapter Plot-Hole Recall (`35` bugs, `LINT-01..07`) | `14.3%` (Surface check) | **`100.0%`** (`3.83 ms` total) | **`+85.7%` plot-hole recall** |
| **`B3`** | 16-Agent Rumor/Lie Contagion & Lie Exposure | `25.0%` / `0.0%` | **`100.0%` / `100.0%`** | **`100%` exact contagion & lie detection** |
| **`B4`** | 100-Tick Living World + 60 FPS 2D Stage Latency | `850.0 ms/tick` (`Smallville`-style) | **`2.365 ms/tick`** (`$0.00` visual cost) | **`359.4x` faster / `-99.7%` tokens** |
| **`B5`** | Butterfly-Effect Blast Radius & 30-Branch Forking | `0.0%` automated | **`100.0%`** in **`0.212 ms`** (`0.179 ms` fork) | **`0.0%` cross-branch contamination** |
| **`B6`** | Live 60 FPS Studio UI Run (`5` Ticks, `25` Mind X-Rays, Interrogate + Butterfly) | `~12,000 ms/frame` (`~$0.40/scene` gen-video) | **`0.751 ms/frame`** (`$0.00` Canvas + WebSpeech) | **`22.2x` faster than 60 FPS budget** |

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
