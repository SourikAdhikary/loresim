"""Native bridge to `crates/loresim-core` (`libloresim_core.dylib` / `.so`) with pure-Python parity."""

from __future__ import annotations

import ctypes
import math
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CANDIDATE_LIBS = [
    _REPO_ROOT / "target" / "release" / "libloresim_core.dylib",
    _REPO_ROOT / "target" / "release" / "libloresim_core.so",
    _REPO_ROOT / "target" / "debug" / "libloresim_core.dylib",
    _REPO_ROOT / "target" / "debug" / "libloresim_core.so",
]

_LIB: ctypes.CDLL | None = None
for _cand in _CANDIDATE_LIBS:
    if _cand.exists():
        try:
            _loaded = ctypes.CDLL(str(_cand))
            _loaded.loresim_rust_version.argtypes = []
            _loaded.loresim_rust_version.restype = ctypes.c_uint32

            _loaded.loresim_dijkstra_shortest_path.argtypes = [
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_int64),
                ctypes.c_size_t,
                ctypes.c_size_t,
            ]
            _loaded.loresim_dijkstra_shortest_path.restype = ctypes.c_int64

            _loaded.loresim_is_within_earshot.argtypes = [
                ctypes.c_double,
                ctypes.c_double,
                ctypes.c_double,
                ctypes.c_double,
                ctypes.c_int32,
                ctypes.c_int32,
                ctypes.c_int32,
            ]
            _loaded.loresim_is_within_earshot.restype = ctypes.c_int32

            _loaded.loresim_effective_earshot_distance.argtypes = [
                ctypes.c_double,
                ctypes.c_double,
                ctypes.c_double,
                ctypes.c_double,
                ctypes.c_int32,
                ctypes.c_int32,
            ]
            _loaded.loresim_effective_earshot_distance.restype = ctypes.c_double

            _loaded.loresim_log_odds_belief_update.argtypes = [
                ctypes.c_double,
                ctypes.c_double,
                ctypes.c_double,
                ctypes.c_double,
            ]
            _loaded.loresim_log_odds_belief_update.restype = ctypes.c_double

            _loaded.loresim_apply_lie_exposure_penalty.argtypes = [
                ctypes.c_double,
                ctypes.c_double,
            ]
            _loaded.loresim_apply_lie_exposure_penalty.restype = ctypes.c_double

            _loaded.loresim_compute_composure_after_evidence.argtypes = [
                ctypes.c_double,
                ctypes.c_double,
                ctypes.c_double,
                ctypes.c_double,
            ]
            _loaded.loresim_compute_composure_after_evidence.restype = ctypes.c_double

            _loaded.loresim_compute_dramatic_irony.argtypes = [
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_double),
                ctypes.POINTER(ctypes.c_double),
                ctypes.POINTER(ctypes.c_double),
            ]
            _loaded.loresim_compute_dramatic_irony.restype = ctypes.c_double

            _loaded.loresim_parabolic_arc_x.argtypes = [
                ctypes.c_double,
                ctypes.c_double,
                ctypes.c_double,
            ]
            _loaded.loresim_parabolic_arc_x.restype = ctypes.c_double

            _loaded.loresim_parabolic_arc_y.argtypes = [
                ctypes.c_double,
                ctypes.c_double,
                ctypes.c_double,
                ctypes.c_double,
            ]
            _loaded.loresim_parabolic_arc_y.restype = ctypes.c_double

            _LIB = _loaded
            break
        except OSError:
            _LIB = None


def is_rust_kernel_loaded() -> bool:
    """Return True if the compiled Rust `loresim-core` shared library is active."""
    return _LIB is not None


def rust_kernel_version() -> int:
    """Return the integer version of the loaded Rust kernel (`200` for v2.0.0)."""
    if _LIB is not None:
        return int(_LIB.loresim_rust_version())
    return 0


def rust_dijkstra_matrix(n: int, adj_flat: list[int], start: int, goal: int) -> int:
    """Compute shortest path over an n x n adjacency matrix via the Rust kernel."""
    if _LIB is not None and n > 0:
        arr_type = ctypes.c_int64 * (n * n)
        arr = arr_type(*adj_flat)
        return int(_LIB.loresim_dijkstra_shortest_path(n, arr, start, goal))
    # Fallback Dijkstra
    if start == goal:
        return 0
    dist = [math.inf] * n
    visited = [False] * n
    dist[start] = 0
    for _ in range(n):
        u = -1
        best = math.inf
        for i in range(n):
            if not visited[i] and dist[i] < best:
                best = dist[i]
                u = i
        if u == -1 or u == goal:
            break
        visited[u] = True
        for v in range(n):
            w = adj_flat[u * n + v]
            if w >= 0 and dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
    return int(dist[goal]) if dist[goal] < math.inf else -1


def rust_log_odds_belief_update(
    prior_conf: float,
    trust_in_speaker: float,
    speaker_asserted_conf: float,
    coupling_k: float = 2.4,
) -> float:
    """Compute trust-weighted Bayesian log-odds belief confidence update."""
    if _LIB is not None:
        return float(
            _LIB.loresim_log_odds_belief_update(
                prior_conf, trust_in_speaker, speaker_asserted_conf, coupling_k
            )
        )
    clamped = max(1e-4, min(1.0 - 1e-4, prior_conf))
    l_prior = math.log(clamped / (1.0 - clamped))
    delta = coupling_k * max(-1.0, min(1.0, trust_in_speaker)) * max(0.0, min(1.0, speaker_asserted_conf))
    return 1.0 / (1.0 + math.exp(-(l_prior + delta)))


def rust_apply_lie_exposure_penalty(current_trust: float, betrayal_penalty: float = 0.65) -> float:
    """Apply trust penalty when a speaker is caught lying against firsthand evidence."""
    if _LIB is not None:
        return float(_LIB.loresim_apply_lie_exposure_penalty(current_trust, betrayal_penalty))
    return max(-1.0, min(1.0, current_trust - abs(betrayal_penalty)))


def rust_compute_composure_after_evidence(
    current_composure: float,
    evidence_weight: float,
    evidence_confidence: float,
    interrogator_pressure: float = 0.5,
) -> float:
    """Compute remaining suspect composure after presenting contradicting evidence."""
    if _LIB is not None:
        return float(
            _LIB.loresim_compute_composure_after_evidence(
                current_composure, evidence_weight, evidence_confidence, interrogator_pressure
            )
        )
    drop = max(0.0, evidence_weight) * max(0.0, min(1.0, evidence_confidence)) * (
        1.0 + max(0.0, min(2.0, interrogator_pressure))
    )
    return max(0.0, min(100.0, current_composure - drop))


def rust_compute_dramatic_irony(
    objective_truths: list[float],
    agent_signed_beliefs: list[float],
    importances: list[float],
) -> float:
    """Compute normalized scene dramatic irony score I_irony in [0.0, 1.0]."""
    n = min(len(objective_truths), len(agent_signed_beliefs), len(importances))
    if n == 0:
        return 0.0
    if _LIB is not None:
        arr_t = (ctypes.c_double * n)(*objective_truths[:n])
        arr_b = (ctypes.c_double * n)(*agent_signed_beliefs[:n])
        arr_w = (ctypes.c_double * n)(*importances[:n])
        return float(_LIB.loresim_compute_dramatic_irony(n, arr_t, arr_b, arr_w))
    total_w = 0.0
    weighted = 0.0
    for i in range(n):
        w = max(0.01, importances[i])
        gap = min(1.0, abs(objective_truths[i] - agent_signed_beliefs[i]) / 2.0)
        weighted += w * gap
        total_w += w
    return weighted / total_w if total_w > 0 else 0.0


def rust_is_within_earshot(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    mode_code: int,
    same_room: bool,
    is_eavesdropping: bool = False,
) -> bool:
    """Check if `(x2, y2)` is within acoustic earshot of `(x1, y1)` under wall attenuation."""
    if _LIB is not None:
        return bool(
            _LIB.loresim_is_within_earshot(
                x1, y1, x2, y2, mode_code, 1 if same_room else 0, 1 if is_eavesdropping else 0
            )
        )
    dist = math.hypot(x2 - x1, y2 - y1)
    eff = dist if same_room else (dist + 1.2 if is_eavesdropping else dist + 4.5)
    radius = {0: 1.8, 1: 6.0, 2: 18.0}.get(mode_code, 6.0)
    return eff <= radius


def rust_parabolic_item_arc(
    x0: float, y0: float, x1: float, y1: float, arc_height: float, u: float
) -> tuple[float, float]:
    """Compute 2D stage coordinates `(x, y)` along a parabolic item transfer trajectory."""
    if _LIB is not None:
        px = float(_LIB.loresim_parabolic_arc_x(x0, x1, u))
        py = float(_LIB.loresim_parabolic_arc_y(y0, y1, arc_height, u))
        return (px, py)
    uc = max(0.0, min(1.0, u))
    x = (1.0 - uc) * x0 + uc * x1
    y = (1.0 - uc) * y0 + uc * y1 - 4.0 * arc_height * uc * (1.0 - uc)
    return (x, y)
