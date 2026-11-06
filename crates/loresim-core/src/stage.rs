//! 60 FPS 2D NPC Puppet physics: spring-damped speech bounce & parabolic item transfer arcs.

/// Computes vertical bounce offset `y_bounce` and squash/stretch scales `(scale_x, scale_y)`
/// for a speaking 2D NPC puppet at normalized syllable time `t in [0.0, 1.0]`.
pub fn spring_damper_speech_bounce(t: f64, amplitude: f64, freq_hz: f64, damping: f64) -> (f64, f64, f64) {
    let tc = t.clamp(0.0, 1.0);
    let omega = std::f64::consts::TAU * freq_hz;
    let y_bounce = amplitude * (omega * tc).sin().abs() * (-damping * tc).exp();
    let scale_x = 1.0 - 0.08 * (y_bounce / amplitude.max(1.0));
    let scale_y = 1.0 + 0.12 * (y_bounce / amplitude.max(1.0));
    (y_bounce, scale_x, scale_y)
}

/// Computes the 2D stage coordinates `(x, y)` of an item flying in a parabolic arc
/// from `(x0, y0)` to `(x1, y1)` at normalized progress `u in [0.0, 1.0]`.
pub fn parabolic_item_arc(x0: f64, y0: f64, x1: f64, y1: f64, arc_height: f64, u: f64) -> (f64, f64) {
    let uc = u.clamp(0.0, 1.0);
    let x = (1.0 - uc) * x0 + uc * x1;
    let linear_y = (1.0 - uc) * y0 + uc * y1;
    let parabola = -4.0 * arc_height * uc * (1.0 - uc);
    (x, linear_y + parabola)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parabolic_arc_midpoint() {
        let (mx, my) = parabolic_item_arc(0.0, 100.0, 200.0, 100.0, 40.0, 0.5);
        assert!((mx - 100.0).abs() < 1e-6);
        assert!((my - 60.0).abs() < 1e-6);
    }
}
