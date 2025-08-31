# backend/tests/test_api_e2e.py
def test_haversine_then_ortools(client):
    # 1) matrix
    dm_req = {
        "adapter": "haversine",
        "origins": [
            {"lat": 37.7749, "lon": -122.4194},
            {"lat": 34.0522, "lon": -118.2437},
        ],
        "destinations": [{"lat": 36.1699, "lon": -115.1398}],
        "mode": "driving",
    }
    r = client.post("/distance-matrix", json=dm_req)
    assert r.status_code == 200, r.text
    j = r.json()
    matrix = j["matrix"] if "matrix" in j else j["data"]["matrix"]

    # Make square 2x2 toy
    d = matrix["distances"]  # 2x1
    square = [[d[0][0], d[0][0]], [d[1][0], d[1][0]]]

    # 2) solve
    solve_req = {
        "solver": "ortools",
        "matrix": {"distances": square},
        "fleet": [{"id": "veh-1", "capacity": [999], "start": 0, "end": 0}],
        "depot_index": 0,
    }
    r2 = client.post("/solver", json=solve_req)
    assert r2.status_code == 200, r2.text
    out = r2.json()
    routes = out["routes"] if "routes" in out else out["data"]["routes"]
    assert routes and isinstance(routes, list)
    assert len(routes[0]["waypoint_ids"]) >= 2
