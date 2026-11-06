//! LoreSim Rust Deterministic Kernel (`loresim-core`).
//! Exposes both idiomatic Rust modules and zero-overhead C-ABI functions (`extern "C"`)
//! loaded by Python via `src/loresim/core/rust_bridge.py` (and usable from Unity/Godot/WASM).

pub mod butterfly;
pub mod epistemic;
pub mod spatial;
pub mod stage;

use std::slice;

#[no_mangle]
pub extern "C" fn loresim_rust_version() -> u32 {
    200 // v2.0.0
}

#[no_mangle]
pub extern "C" fn loresim_dijkstra_shortest_path(
    n: usize,
    adj_ptr: *const i64,
    start: usize,
    goal: usize,
) -> i64 {
    if adj_ptr.is_null() || n == 0 {
        return -1;
    }
    let adj = unsafe { slice::from_raw_parts(adj_ptr, n * n) };
    spatial::dijkstra_matrix(n, adj, start, goal)
}

#[no_mangle]
pub extern "C" fn loresim_is_within_earshot(
    x1: f64,
    y1: f64,
    x2: f64,
    y2: f64,
    mode: i32,
    same_room: i32,
    is_eavesdropping: i32,
) -> i32 {
    if spatial::is_within_earshot(
        x1,
        y1,
        x2,
        y2,
        mode,
        same_room != 0,
        is_eavesdropping != 0,
    ) {
        1
    } else {
        0
    }
}

#[no_mangle]
pub extern "C" fn loresim_effective_earshot_distance(
    x1: f64,
    y1: f64,
    x2: f64,
    y2: f64,
    same_room: i32,
    is_eavesdropping: i32,
) -> f64 {
    spatial::effective_earshot_distance(x1, y1, x2, y2, same_room != 0, is_eavesdropping != 0)
}

#[no_mangle]
pub extern "C" fn loresim_log_odds_belief_update(
    prior_conf: f64,
    trust_in_speaker: f64,
    speaker_asserted_conf: f64,
    coupling_k: f64,
) -> f64 {
    epistemic::log_odds_belief_update(prior_conf, trust_in_speaker, speaker_asserted_conf, coupling_k)
}

#[no_mangle]
pub extern "C" fn loresim_apply_lie_exposure_penalty(
    current_trust: f64,
    betrayal_penalty: f64,
) -> f64 {
    epistemic::apply_lie_exposure_trust_penalty(current_trust, betrayal_penalty)
}

#[no_mangle]
pub extern "C" fn loresim_compute_composure_after_evidence(
    current_composure: f64,
    evidence_weight: f64,
    evidence_confidence: f64,
    interrogator_pressure: f64,
) -> f64 {
    epistemic::compute_composure_after_evidence(
        current_composure,
        evidence_weight,
        evidence_confidence,
        interrogator_pressure,
    )
}

#[no_mangle]
pub extern "C" fn loresim_compute_dramatic_irony(
    n: usize,
    truths_ptr: *const f64,
    beliefs_ptr: *const f64,
    weights_ptr: *const f64,
) -> f64 {
    if n == 0 || truths_ptr.is_null() || beliefs_ptr.is_null() || weights_ptr.is_null() {
        return 0.0;
    }
    let truths = unsafe { slice::from_raw_parts(truths_ptr, n) };
    let beliefs = unsafe { slice::from_raw_parts(beliefs_ptr, n) };
    let weights = unsafe { slice::from_raw_parts(weights_ptr, n) };
    epistemic::compute_dramatic_irony(truths, beliefs, weights)
}

#[no_mangle]
pub extern "C" fn loresim_parabolic_arc_x(
    x0: f64,
    x1: f64,
    u: f64,
) -> f64 {
    let (x, _) = stage::parabolic_item_arc(x0, 0.0, x1, 0.0, 0.0, u);
    x
}

#[no_mangle]
pub extern "C" fn loresim_parabolic_arc_y(
    y0: f64,
    y1: f64,
    arc_height: f64,
    u: f64,
) -> f64 {
    let (_, y) = stage::parabolic_item_arc(0.0, y0, 0.0, y1, arc_height, u);
    y
}
