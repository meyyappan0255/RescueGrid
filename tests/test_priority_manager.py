"""Unit tests for the in-memory ambulance priority manager."""
from central_server.priority_manager import AmbulanceRequest, PriorityManager


def request(ambulance_id, criticality=3, eta=10, junction_id="JN-1"):
    return AmbulanceRequest(
        ambulance_id=ambulance_id,
        junction_id=junction_id,
        eta_seconds=eta,
        criticality=criticality,
        dist_to_junction=100,
        trip_remaining_m=2000,
        requested_at=1_700_000_000,
    )


def test_register_replaces_same_ambulance_request():
    manager = PriorityManager()
    manager.register(request("AMB-1", eta=40))
    manager.register(request("AMB-1", eta=12))
    assert len(manager.junction_status("JN-1")["requests"]) == 1
    assert manager.get_winner("JN-1").eta_seconds == 12


def test_winner_is_none_for_empty_junction():
    assert PriorityManager().get_winner("JN-1") is None


def test_imminent_request_with_higher_criticality_wins():
    manager = PriorityManager()
    manager.register(request("AMB-LOW", criticality=1, eta=8))
    manager.register(request("AMB-HIGH", criticality=5, eta=10))
    assert manager.get_winner("JN-1").ambulance_id == "AMB-HIGH"


def test_deregister_removes_request():
    manager = PriorityManager()
    manager.register(request("AMB-1"))
    manager.deregister("AMB-1", "JN-1")
    assert manager.get_winner("JN-1") is None


def test_requests_for_different_junctions_are_isolated():
    manager = PriorityManager()
    manager.register(request("AMB-1", junction_id="JN-1"))
    manager.register(request("AMB-2", junction_id="JN-2"))
    assert manager.get_winner("JN-1").ambulance_id == "AMB-1"
    assert manager.get_winner("JN-2").ambulance_id == "AMB-2"
