"""Basic tests for route-planning helpers."""
import pytest

from central_server.route_predictor import Node, RoadGraph, RoutePlanner, haversine


def test_haversine_same_point_is_zero():
    assert haversine(13.0, 80.0, 13.0, 80.0) == pytest.approx(0.0)


def test_route_planner_finds_shortest_distance_path():
    graph = RoadGraph()
    for node_id, lat, lon in [
        ("A", 13.0, 80.0),
        ("B", 13.1, 80.1),
        ("C", 13.2, 80.2),
    ]:
        graph.add_node(Node(id=node_id, lat=lat, lon=lon))
    graph.add_edge("A", "B", distance_m=10)
    graph.add_edge("B", "C", distance_m=10)
    graph.add_edge("A", "C", distance_m=100)
    route = RoutePlanner(graph).find_route("A", "C")
    assert route == ["A", "B", "C"]


def test_eta_uses_floor_speed_to_avoid_zero_division():
    graph = RoadGraph()
    graph.add_node(Node(id="A", lat=13.0, lon=80.0))
    graph.add_node(Node(id="B", lat=13.1, lon=80.1))
    graph.add_edge("A", "B", distance_m=100)
    etas = RoutePlanner(graph).calculate_etas(["A", "B"], current_speed_kmh=0)
    assert etas["B"] == pytest.approx(36.0)
