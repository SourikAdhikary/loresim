"""Spatial topology manager and Rust-accelerated Dijkstra minimum travel-time solver."""

from __future__ import annotations

import uuid

from loresim.core.rust_bridge import rust_dijkstra_matrix
from loresim.core.types import LocationNode, RouteEdge
from loresim.storage.db import SQLiteDatabase


class SpatialTopology:
    """Manages locations, travel routes, and shortest-path travel duration bounds."""

    def __init__(self, db: SQLiteDatabase) -> None:
        self.db = db

    def add_location(
        self,
        location_id: str,
        name: str,
        region: str = "Core",
        parent_location_id: str | None = None,
        x_coord: float = 0.0,
        y_coord: float = 0.0,
        description: str = "",
    ) -> LocationNode:
        node = LocationNode(
            location_id=location_id,
            name=name,
            region=region,
            parent_location_id=parent_location_id,
            x_coord=float(x_coord),
            y_coord=float(y_coord),
            description=description,
        )
        with self.db.transaction():
            self.db.execute(
                """
                INSERT OR REPLACE INTO locations
                (location_id, name, region, parent_location_id, x_coord, y_coord, description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node.location_id,
                    node.name,
                    node.region,
                    node.parent_location_id,
                    node.x_coord,
                    node.y_coord,
                    node.description,
                ),
            )
        return node

    def add_route(
        self,
        from_location_id: str,
        to_location_id: str,
        travel_minutes: int,
        transport_mode: str = "walk",
        bidirectional: bool = True,
        route_id: str | None = None,
    ) -> RouteEdge:
        rid = route_id or f"route_{uuid.uuid4().hex[:10]}"
        edge = RouteEdge(
            route_id=rid,
            from_location_id=from_location_id,
            to_location_id=to_location_id,
            transport_mode=transport_mode,
            travel_minutes=max(1, int(travel_minutes)),
            bidirectional=bidirectional,
        )
        with self.db.transaction():
            self.db.execute(
                """
                INSERT OR REPLACE INTO routes
                (route_id, from_location_id, to_location_id, transport_mode, travel_minutes, bidirectional)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    edge.route_id,
                    edge.from_location_id,
                    edge.to_location_id,
                    edge.transport_mode,
                    edge.travel_minutes,
                    1 if edge.bidirectional else 0,
                ),
            )
        return edge

    def list_locations(self) -> list[LocationNode]:
        rows = self.db.fetchall("SELECT * FROM locations ORDER BY location_id")
        return [
            LocationNode(
                location_id=str(r["location_id"]),
                name=str(r["name"]),
                region=str(r["region"]),
                parent_location_id=r["parent_location_id"],
                x_coord=float(r["x_coord"]),
                y_coord=float(r["y_coord"]),
                description=str(r["description"]),
            )
            for r in rows
        ]

    def get_location(self, location_id: str) -> LocationNode | None:
        r = self.db.fetchone("SELECT * FROM locations WHERE location_id = ?", (location_id,))
        if r is None:
            return None
        return LocationNode(
            location_id=str(r["location_id"]),
            name=str(r["name"]),
            region=str(r["region"]),
            parent_location_id=r["parent_location_id"],
            x_coord=float(r["x_coord"]),
            y_coord=float(r["y_coord"]),
            description=str(r["description"]),
        )

    def list_routes(self) -> list[RouteEdge]:
        rows = self.db.fetchall("SELECT * FROM routes ORDER BY route_id")
        return [
            RouteEdge(
                route_id=str(r["route_id"]),
                from_location_id=str(r["from_location_id"]),
                to_location_id=str(r["to_location_id"]),
                transport_mode=str(r["transport_mode"]),
                travel_minutes=int(r["travel_minutes"]),
                bidirectional=bool(r["bidirectional"]),
            )
            for r in rows
        ]

    def min_travel_minutes(self, from_loc: str, to_loc: str) -> int:
        """Compute minimum travel minutes between two locations using the Rust Dijkstra kernel.

        Returns `0` if `from_loc == to_loc`, or `-1` if no path exists.
        """
        if from_loc == to_loc:
            return 0
        locs = [loc.location_id for loc in self.list_locations()]
        if from_loc not in locs or to_loc not in locs:
            return -1
        idx_map = {lid: i for i, lid in enumerate(locs)}
        n = len(locs)
        adj = [-1] * (n * n)
        for i in range(n):
            adj[i * n + i] = 0
        for edge in self.list_routes():
            u = idx_map.get(edge.from_location_id)
            v = idx_map.get(edge.to_location_id)
            if u is None or v is None:
                continue
            cur = adj[u * n + v]
            if cur < 0 or edge.travel_minutes < cur:
                adj[u * n + v] = edge.travel_minutes
            if edge.bidirectional:
                cur_rev = adj[v * n + u]
                if cur_rev < 0 or edge.travel_minutes < cur_rev:
                    adj[v * n + u] = edge.travel_minutes
        return rust_dijkstra_matrix(n, adj, idx_map[from_loc], idx_map[to_loc])
