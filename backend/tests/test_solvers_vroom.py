import copy
import pytest

# no import tricks here; conftest already makes backend importable
# and provides the `client` fixture that starts the app & loads plugins

TOY_VROOM_COORD = {
    "matrix": {
        "distances": [[0, 1, 2], [1, 0, 1], [2, 1, 0]],
        "durations": [[0, 600, 1200], [600, 0, 600], [1200, 600, 0]],
        "coordinates": [
            [-122.4194, 37.7749],
            [-118.2437, 34.0522],
            [-115.1398, 36.1699],
        ],
    },
    "fleet": [{"id": "veh-1", "capacity": [999], "start": 0, "end": 0}],
    "depot_index": 0,
}


def test_vroom_coordinate_mode(client):
    # Ensure solvers are registered (app lifespan already ran via client)
    from services.solver_factory import _solver_registry

    if "vroom" not in _solver_registry:
        pytest.skip("vroom solver not registered")

    payload = {"solver": "vroom", **copy.deepcopy(TOY_VROOM_COORD)}
    r = client.post("/solver", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "routes" in data and isinstance(data["routes"], list)
