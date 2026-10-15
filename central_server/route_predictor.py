# central_server/route_predictor.py
# ─────────────────────────────────────────────────────────────
# RescueGrid — Route Prediction & ETA Calculator
# Uses A* on a graph of road junctions to predict the
# ambulance's most likely path to the destination hospital
# and estimates arrival time at each upcoming junction.
# ─────────────────────────────────────────────────────────────

import math
import heapq
from dataclasses import dataclass, field
from typing import Optional

# ── Data structures ──────────────────────────────────────────

@dataclass
class Node:
    """A junction / waypoint in the road graph."""
    id:        str
    lat:       float
    lon:       float
    name:      str = ""

@dataclass(order=True)
class _PQItem:
    priority: float
    node_id:  str = field(compare=False)

# ── Haversine distance ───────────────────────────────────────

def haversine(lat1, lon1, lat2, lon2) -> float:
    """Return distance in metres between two WGS-84 coordinates."""
    R = 6_371_000  # Earth radius in metres
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(Δλ/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# ── Road graph ───────────────────────────────────────────────

class RoadGraph:
    """Directed weighted graph of junctions linked by roads."""

    def __init__(self):
        self.nodes: dict[str, Node] = {}
        # edges[node_id] = [(neighbour_id, distance_m, speed_limit_kmh)]
        self.edges: dict[str, list[tuple]] = {}

    def add_node(self, node: Node):
        self.nodes[node.id] = node
        if node.id not in self.edges:
            self.edges[node.id] = []

    def add_edge(self, from_id: str, to_id: str,
                 distance_m: Optional[float] = None,
                 speed_kmh: float = 40.0):
        if distance_m is None:
            n1, n2 = self.nodes[from_id], self.nodes[to_id]
            distance_m = haversine(n1.lat, n1.lon, n2.lat, n2.lon)
        self.edges[from_id].append((to_id, distance_m, speed_kmh))

    def nearest_node(self, lat: float, lon: float) -> Optional[str]:
        """Find the graph node closest to given coordinates."""
        best_id, best_dist = None, float("inf")
        for nid, node in self.nodes.items():
            d = haversine(lat, lon, node.lat, node.lon)
            if d < best_dist:
                best_dist, best_id = d, nid
        return best_id

# ── A* Route Planner ─────────────────────────────────────────

class RoutePlanner:
    def __init__(self, graph: RoadGraph):
        self.graph = graph

    def find_route(self, start_id: str, goal_id: str) -> Optional[list[str]]:
        """Return ordered list of node IDs from start to goal, or None."""
        if start_id == goal_id:
            return [start_id]

        g_score = {start_id: 0.0}
        came_from: dict[str, str] = {}
        pq = [_PQItem(self._h(start_id, goal_id), start_id)]

        while pq:
            item = heapq.heappop(pq)
            current = item.node_id

            if current == goal_id:
                return self._reconstruct(came_from, current)

            for neighbour, dist_m, _ in self.graph.edges.get(current, []):
                tentative = g_score[current] + dist_m
                if tentative < g_score.get(neighbour, float("inf")):
                    came_from[neighbour] = current
                    g_score[neighbour] = tentative
                    f = tentative + self._h(neighbour, goal_id)
                    heapq.heappush(pq, _PQItem(f, neighbour))

        return None   # No path found

    def calculate_etas(self, route: list[str],
                       current_speed_kmh: float = 40.0) -> dict[str, float]:
        """Return {node_id: eta_seconds_from_now} for each junction on route."""
        etas: dict[str, float] = {}
        elapsed = 0.0
        speed_ms = max(current_speed_kmh, 10.0) / 3.6  # avoid division by 0

        for i in range(len(route) - 1):
            from_id, to_id = route[i], route[i + 1]
            edges = self.graph.edges.get(from_id, [])
            seg_dist = next((d for (nb, d, _) in edges if nb == to_id), 0.0)
            seg_speed = next((s for (nb, _, s) in edges if nb == to_id), 40.0)
            seg_speed_ms = max(seg_speed, 10.0) / 3.6
            elapsed += seg_dist / seg_speed_ms
            etas[to_id] = round(elapsed, 1)

        return etas

    def _h(self, node_id: str, goal_id: str) -> float:
        """Heuristic: straight-line distance (admissible)."""
        n, g = self.graph.nodes[node_id], self.graph.nodes[goal_id]
        return haversine(n.lat, n.lon, g.lat, g.lon)

    @staticmethod
    def _reconstruct(came_from: dict, current: str) -> list[str]:
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path

# ── Demo graph builder (replace with real map data) ──────────

def build_demo_graph() -> RoadGraph:
    """
    Build a small demo graph for testing.
    Replace node coordinates with your actual city junction data.
    In production, load from a GeoJSON / OSRM road network.
    """
    g = RoadGraph()
    junctions = [
        Node("JN001", 13.0827, 80.2707, "Central Station Junction"),
        Node("JN002", 13.0843, 80.2745, "Anna Salai North"),
        Node("JN003", 13.0860, 80.2780, "Gemini Flyover"),
        Node("JN004", 13.0878, 80.2815, "Nungambakkam"),
        Node("JN005", 13.0900, 80.2840, "Chetpet"),
        Node("HOSP",  13.0920, 80.2870, "Apollo Hospital"),
    ]
    for jn in junctions:
        g.add_node(jn)

    # Bidirectional road links with speed limits
    links = [
        ("JN001", "JN002", 50), ("JN002", "JN001", 50),
        ("JN002", "JN003", 50), ("JN003", "JN002", 50),
        ("JN003", "JN004", 40), ("JN004", "JN003", 40),
        ("JN004", "JN005", 40), ("JN005", "JN004", 40),
        ("JN005", "HOSP",  30), ("HOSP",  "JN005", 30),
        # Shortcut
        ("JN001", "JN003", 60), ("JN003", "JN001", 60),
    ]
    for (a, b, spd) in links:
        g.add_edge(a, b, speed_kmh=spd)

    return g
