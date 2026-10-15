"""Hardware-independent validation tests for RescueGrid Pydantic models."""
import pytest
from pydantic import ValidationError

from central_server.models import AmbulanceUpdate, GPSData, SignalCommand, SignalState


def valid_update(**overrides):
    payload = {
        "ambulance_id": "AMB-TEST",
        "priority_active": True,
        "criticality": 4,
        "gps": {
            "latitude": 13.0827,
            "longitude": 80.2707,
            "speed_kmh": 35.0,
            "heading": 90.0,
            "altitude": 10.0,
            "satellites": 7,
            "fix_quality": 1,
        },
        "timestamp": 1717027200.0,
    }
    payload.update(overrides)
    return payload


def test_valid_ambulance_update_parses():
    update = AmbulanceUpdate.model_validate(valid_update())
    assert update.ambulance_id == "AMB-TEST"
    assert update.gps.latitude == pytest.approx(13.0827)
    assert update.priority_active is True


@pytest.mark.parametrize("criticality", [0, 6, -1])
def test_criticality_out_of_range_is_rejected(criticality):
    with pytest.raises(ValidationError):
        AmbulanceUpdate.model_validate(valid_update(criticality=criticality))


def test_gps_coordinates_can_be_missing_in_model():
    gps = GPSData(latitude=None, longitude=None)
    assert gps.latitude is None
    assert gps.longitude is None


def test_signal_command_uses_enum_state():
    command = SignalCommand(
        junction_id="JN-TEST",
        ambulance_id="AMB-TEST",
        state=SignalState.EMERGENCY,
        green_direction=1,
        duration_seconds=15,
        issued_at="2026-01-01T00:00:00Z",
    )
    assert command.state == SignalState.EMERGENCY
