//! Spatial topology Dijkstra shortest-path solver and 2D stage acoustic earshot physics.

use std::cmp::Ordering;
use std::collections::BinaryHeap;

#[derive(Copy, Clone, Eq, PartialEq)]
struct State {
    cost: i64,
    node: usize,
}

impl Ord for State {
    fn cmp(&self, other: &Self) -> Ordering {
        other.cost.cmp(&self.cost).then_with(|| self.node.cmp(&other.node))
    }
}

impl PartialOrd for State {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

/// Computes the shortest travel time between `start` and `goal` over an `n x n` adjacency matrix
/// (`adj[u * n + v]`, where `< 0` means no direct edge). Returns `-1` if unreachable.
pub fn dijkstra_matrix(n: usize, adj: &[i64], start: usize, goal: usize) -> i64 {
    if start >= n || goal >= n || adj.len() < n * n {
        return -1;
    }
    if start == goal {
        return 0;
    }
    let mut dist = vec![i64::MAX; n];
    let mut heap = BinaryHeap::new();

    dist[start] = 0;
    heap.push(State { cost: 0, node: start });

    while let Some(State { cost, node }) = heap.pop() {
        if node == goal {
            return cost;
        }
        if cost > dist[node] {
            continue;
        }
        let row_offset = node * n;
        for next in 0..n {
            let weight = adj[row_offset + next];
            if weight >= 0 {
                let next_cost = cost.saturating_add(weight);
                if next_cost < dist[next] {
                    dist[next] = next_cost;
                    heap.push(State {
                        cost: next_cost,
                        node: next,
                    });
                }
            }
        }
    }
    -1
}

/// Acoustic modality radius in meters:
/// mode 0 = WHISPER (1.8m), mode 1 = NORMAL_SPEECH (6.0m), mode 2 = SHOUT (18.0m)
pub fn earshot_radius_meters(mode: i32) -> f64 {
    match mode {
        0 => 1.8,
        1 => 6.0,
        2 => 18.0,
        _ => 6.0,
    }
}

/// Computes effective acoustic distance between `(x1, y1)` and `(x2, y2)` accounting for
/// wall attenuation (`4.5m` penalty) and doorway eavesdropping stance (`1.2m` penalty).
pub fn effective_earshot_distance(
    x1: f64,
    y1: f64,
    x2: f64,
    y2: f64,
    same_room: bool,
    is_eavesdropping_at_door: bool,
) -> f64 {
    let dx = x2 - x1;
    let dy = y2 - y1;
    let euclidean = (dx * dx + dy * dy).sqrt();
    if same_room {
        euclidean
    } else if is_eavesdropping_at_door {
        euclidean + 1.2
    } else {
        euclidean + 4.5
    }
}

pub fn is_within_earshot(
    x1: f64,
    y1: f64,
    x2: f64,
    y2: f64,
    mode: i32,
    same_room: bool,
    is_eavesdropping_at_door: bool,
) -> bool {
    let eff = effective_earshot_distance(x1, y1, x2, y2, same_room, is_eavesdropping_at_door);
    eff <= earshot_radius_meters(mode)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_dijkstra_shortest_path() {
        // 3 locations: 0 -> 1 (10m), 1 -> 2 (15m), 0 -> 2 direct (40m)
        let adj = vec![
            0, 10, 40,
            10, 0, 15,
            40, 15, 0,
        ];
        assert_eq!(dijkstra_matrix(3, &adj, 0, 2), 25);
        assert_eq!(dijkstra_matrix(3, &adj, 0, 0), 0);
    }

    #[test]
    fn test_earshot_physics() {
        // Whisper (mode 0 = 1.8m): 1.2m away in same room -> heard
        assert!(is_within_earshot(0.0, 0.0, 1.2, 0.0, 0, true, false));
        // Whisper 3.0m away in same room -> not heard
        assert!(!is_within_earshot(0.0, 0.0, 3.0, 0.0, 0, true, false));
        // Normal speech across wall without eavesdropping (2.0m + 4.5m = 6.5m > 6.0m) -> not heard
        assert!(!is_within_earshot(0.0, 0.0, 2.0, 0.0, 1, false, false));
        // Same position but eavesdropping at door (2.0m + 1.2m = 3.2m <= 6.0m) -> heard!
        assert!(is_within_earshot(0.0, 0.0, 2.0, 0.0, 1, false, true));
    }
}
