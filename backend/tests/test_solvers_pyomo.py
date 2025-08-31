# backend/tests/test_solvers_pyomo.py
import copy
import pytest

from .conftest import solver_available

TOY_TW = {
    "matrix": {
        "distances": [[0, 5, 7], [5, 0, 3], [7, 3, 0]],
        "durations": [[0, 300, 420], [300, 0, 180], [420, 180, 0]],
    },
    "fleet": [
        {
            "id": "veh-1",
            "capacity": [10],
            "time_window": [0, 3600],
            "start": 0,
            "end": 0,
        }
    ],
    "depot_index": 0,
    "demands": [0, 4, 4],
    "node_time_windows": [[0, 3600], [0, 3600], [600, 3600]],
    "node_service_times": [0, 120, 120],
}


@pytest.mark.skipif(not solver_available("cbc"), reason="CBC not found in PATH")
def test_pyomo_cvrptw(client):
    payload = {"solver": "pyomo", **copy.deepcopy(TOY_TW)}
    r = client.post("/solver", json=payload)
    assert r.status_code == 200, r.text
    j = r.json()
    assert ("routes" in j) or ("routes" in j.get("data", {}))
