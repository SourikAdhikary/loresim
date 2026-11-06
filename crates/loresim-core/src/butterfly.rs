//! Sub-millisecond Causal Dependency & "Butterfly Effect" Blast-Radius graph propagation.

/// Given `n` events (0..n) and a list of directed causal dependency edges `(parent_idx, child_idx)`,
/// computes all downstream events transitively broken when `disabled_event_idx` is disabled or mutated.
pub fn trace_causal_blast_radius(
    n: usize,
    edges: &[(usize, usize)],
    disabled_event_idx: usize,
) -> Vec<usize> {
    if disabled_event_idx >= n {
        return Vec::new();
    }
    let mut broken = vec![false; n];
    let mut queue = Vec::new();
    broken[disabled_event_idx] = true;
    queue.push(disabled_event_idx);

    let mut head = 0;
    while head < queue.len() {
        let curr = queue[head];
        head += 1;
        for &(u, v) in edges {
            if u == curr && v < n && !broken[v] {
                broken[v] = true;
                queue.push(v);
            }
        }
    }

    let mut affected: Vec<usize> = queue.into_iter().filter(|&idx| idx != disabled_event_idx).collect();
    affected.sort_unstable();
    affected
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_butterfly_blast_radius() {
        // Event 1 -> Event 3 -> Event 5, Event 2 -> Event 4
        let edges = vec![(1, 3), (3, 5), (2, 4)];
        let affected = trace_causal_blast_radius(6, &edges, 1);
        assert_eq!(affected, vec![3, 5]);
    }
}
