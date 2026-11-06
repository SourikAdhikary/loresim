"""Unit tests for the native Rust bridge (`libloresim_core`), Spatial Dijkstra, and Linear Inventory."""

from __future__ import annotations

from loresim.core.rust_bridge import (
    is_rust_kernel_loaded,
    rust_dijkstra_matrix,
    rust_is_within_earshot,
    rust_kernel_version,
    rust_parabolic_item_arc,
)
from loresim.interfaces.engine import LoreSimEngine


def test_rust_kernel_bridge_active() -> None:
    assert is_rust_kernel_loaded() is True
    assert rust_kernel_version() == 200
    assert rust_dijkstra_matrix(3, [0, 10, 50, 10, 0, 15, 50, 15, 0], 0, 2) == 25
    assert rust_is_within_earshot(0.0, 0.0, 1.4, 0.0, 0, True, False) is True
    assert rust_is_within_earshot(0.0, 0.0, 3.0, 0.0, 0, True, False) is False
    mx, my = rust_parabolic_item_arc(0.0, 100.0, 200.0, 100.0, 40.0, 0.5)
    assert abs(mx - 100.0) < 1e-6
    assert abs(my - 60.0) < 1e-6


def test_spatial_topology_and_inventory_conservation(engine: LoreSimEngine) -> None:
    engine.spatial.add_location("town", "Town")
    engine.spatial.add_location("castle", "Castle")
    engine.spatial.add_location("port", "Port")
    engine.spatial.add_route("town", "castle", travel_minutes=20)
    engine.spatial.add_route("castle", "port", travel_minutes=35)

    assert engine.spatial.min_travel_minutes("town", "port") == 55

    engine.agents.register_agent("alice", "Alice", initial_location_id="town")
    engine.agents.register_agent("bob", "Bob", initial_location_id="town")
    engine.inventory.register_item("crown", "Royal Crown", is_unique=True, initial_holder_id="alice", tick=0)

    assert [i.item_id for i in engine.inventory.get_agent_held_items("alice", query_tick=0)] == ["crown"]
    engine.record_event(
        tick=1,
        location_id="town",
        actor_id="alice",
        target_ids=("bob",),
        event_type="GIVE_ITEM",
        item_id="crown",
    )
    assert engine.inventory.get_agent_held_items("alice", query_tick=1) == []
    assert [i.item_id for i in engine.inventory.get_agent_held_items("bob", query_tick=1)] == ["crown"]
