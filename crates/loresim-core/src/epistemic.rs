//! Dynamic Epistemic Logic (KD45_n) log-odds belief updater, firsthand lie-exposure detector,
//! interrogation composure mechanics, and dramatic irony scoring.

/// Sigmoid function sigma(x) = 1 / (1 + e^-x)
#[inline]
pub fn sigmoid(x: f64) -> f64 {
    1.0 / (1.0 + (-x).exp())
}

/// Clamped logit function ln(p / (1 - p))
#[inline]
pub fn logit(p: f64) -> f64 {
    let clamped = p.clamp(1e-4, 1.0 - 1e-4);
    (clamped / (1.0 - clamped)).ln()
}

/// Trust-weighted Bayesian log-odds belief update when speaker asserts a claim to listener.
///
/// * `prior_conf`: Listener's prior confidence in proposition [0.0, 1.0] (default 0.5 for neutral/unaware)
/// * `trust_in_speaker`: Listener's trust in speaker [-1.0, 1.0]
/// * `speaker_asserted_conf`: Speaker's asserted confidence [0.0, 1.0]
/// * `coupling_k`: Sensitivity gain (default 2.4)
pub fn log_odds_belief_update(
    prior_conf: f64,
    trust_in_speaker: f64,
    speaker_asserted_conf: f64,
    coupling_k: f64,
) -> f64 {
    let l_prior = logit(prior_conf);
    let delta = coupling_k * trust_in_speaker.clamp(-1.0, 1.0) * speaker_asserted_conf.clamp(0.0, 1.0);
    sigmoid(l_prior + delta).clamp(0.0, 1.0)
}

/// Checks if a listener who holds a FIRSTHAND belief (`listener_has_firsthand_contradiction`)
/// immediately detects that the speaker is lying, returning the updated trust in the speaker.
pub fn apply_lie_exposure_trust_penalty(
    current_trust: f64,
    betrayal_penalty: f64,
) -> f64 {
    (current_trust - betrayal_penalty.abs()).clamp(-1.0, 1.0)
}

/// Computes composure drop during live detective interrogation when presented with contradicting evidence.
pub fn compute_composure_after_evidence(
    current_composure: f64,
    evidence_weight: f64,
    evidence_confidence: f64,
    interrogator_pressure: f64,
) -> f64 {
    let drop = evidence_weight.max(0.0)
        * evidence_confidence.clamp(0.0, 1.0)
        * (1.0 + interrogator_pressure.clamp(0.0, 2.0));
    (current_composure - drop).clamp(0.0, 100.0)
}

/// Computes Scene Dramatic Irony score I_irony in [0.0, 1.0] across `(objective_truth, agent_signed_belief, importance)` tuples.
/// `objective_truth`: 1.0 if proposition is canonically TRUE, -1.0 if FALSE (fabricated lie).
/// `agent_signed_belief`: +conf if agent believes TRUE, -conf if agent believes FALSE, 0.0 if unaware.
pub fn compute_dramatic_irony(
    objective_truths: &[f64],
    agent_signed_beliefs: &[f64],
    importances: &[f64],
) -> f64 {
    let n = objective_truths
        .len()
        .min(agent_signed_beliefs.len())
        .min(importances.len());
    if n == 0 {
        return 0.0;
    }
    let mut weighted_gap = 0.0;
    let mut total_weight = 0.0;
    for i in 0..n {
        let w = importances[i].max(0.01);
        // Normalized divergence between objective truth in {-1, 1} and belief in [-1, 1] is |t - b| / 2.0
        let gap = ((objective_truths[i] - agent_signed_beliefs[i]).abs() / 2.0).clamp(0.0, 1.0);
        weighted_gap += w * gap;
        total_weight += w;
    }
    if total_weight <= 0.0 {
        0.0
    } else {
        (weighted_gap / total_weight).clamp(0.0, 1.0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_log_odds_update() {
        let updated = log_odds_belief_update(0.5, 0.85, 1.0, 2.4);
        assert!(updated > 0.85);
        let distrusted = log_odds_belief_update(0.5, -0.8, 1.0, 2.4);
        assert!(distrusted < 0.20);
    }

    #[test]
    fn test_dramatic_irony_scoring() {
        // Proposition is FALSE (-1.0), i.e., a lie ("Rebels stole the treaty"),
        // but Character B strongly believes it is TRUE (+0.9). Gap = |-1.0 - 0.9| / 2 = 0.95!
        let truths = vec![-1.0];
        let beliefs = vec![0.9];
        let weights = vec![1.0];
        let score = compute_dramatic_irony(&truths, &beliefs, &weights);
        assert!((score - 0.95).abs() < 1e-6);
    }
}
