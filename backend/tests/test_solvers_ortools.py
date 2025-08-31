# backend/tests/test_solvers_ortools.py
import copy

TOY_CVRP = {
    "matrix": {"distances": [[0, 5, 7], [5, 0, 3], [7, 3, 0]]},
    "fleet": [{"id": "veh-1", "capacity": [999], "start": 0, "end": 0}],
    "depot_index": 0,
}

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

TOY_PD = {
    "matrix": {"distances": [[0, 5, 7], [5, 0, 3], [7, 3, 0]]},
    "fleet": [{"id": "veh-1", "capacity": [10], "start": 0, "end": 0}],
    "depot_index": 0,
    "demands": [0, 4, -4],
    "pickup_delivery_pairs": [{"pickup": 1, "delivery": 2}],
}


def _extract_routes(resp_json):
    if "routes" in resp_json:
        return resp_json["routes"]
    if "data" in resp_json and "routes" in resp_json["data"]:
        return resp_json["data"]["routes"]
    raise AssertionError(f"cannot find routes in {resp_json}")


def test_ortools_baseline(client):
    payload = {"solver": "ortools", **copy.deepcopy(TOY_CVRP)}
    r = client.post("/solver", json=payload)
    assert r.status_code == 200, r.text
    routes = _extract_routes(r.json())
    assert routes and isinstance(routes, list)
    assert len(routes[0]["waypoint_ids"]) >= 2


def test_ortools_time_windows(client):
    payload = {"solver": "ortools", **copy.deepcopy(TOY_TW)}
    r = client.post("/solver", json=payload)
    assert r.status_code == 200, r.text
    routes = _extract_routes(r.json())
    assert routes and isinstance(routes, list)


def test_ortools_pickup_delivery(client):
    payload = {"solver": "ortools", **copy.deepcopy(TOY_PD)}
    r = client.post("/solver", json=payload)
    assert r.status_code == 200, r.text
    routes = _extract_routes(r.json())
    assert routes and isinstance(routes, list)
