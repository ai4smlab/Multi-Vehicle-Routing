# backend/tests/test_adapters.py
import pytest


def _matrix_from_response(resp_json):
    """Handle both {data:{matrix}} and {matrix} shapes."""
    if "matrix" in resp_json:
        return resp_json["matrix"]
    if "data" in resp_json and "matrix" in resp_json["data"]:
        return resp_json["data"]["matrix"]
    # sometimes {data:{...}} where {...} is already a MatrixResult dump
    if "data" in resp_json and isinstance(resp_json["data"], dict):
        if "distances" in resp_json["data"]:
            return resp_json["data"]
        if "matrix" in resp_json["data"]:
            return resp_json["data"]["matrix"]
    raise AssertionError(f"Could not find matrix in response: {resp_json}")


def _as_km(x: float) -> float:
    # If value is very large, assume meters and convert to km
    return x / 1000.0 if x > 10000 else x


@pytest.mark.parametrize(
    "o,d,expected_range_km",
    [
        ((37.7749, -122.4194), (34.0522, -118.2437), (500, 700)),  # SF→LA ~560 km
    ],
)
def test_haversine_adapter(client, o, d, expected_range_km):
    payload = {
        "adapter": "haversine",
        "origins": [{"lat": o[0], "lon": o[1]}],
        "destinations": [{"lat": d[0], "lon": d[1]}],
        "mode": "driving",
    }
    r = client.post("/distance-matrix", json=payload)
    assert r.status_code == 200, r.text

    matrix = _matrix_from_response(r.json())
    assert "distances" in matrix
    assert len(matrix["distances"]) == 1 and len(matrix["distances"][0]) == 1

    val = float(matrix["distances"][0][0])
    km = _as_km(val)
    lo, hi = expected_range_km
    assert lo <= km <= hi, f"expected {lo}..{hi} km, got {km} ({val} raw)"


@pytest.mark.online
def test_openrouteservice_adapter(client, has_ors):
    if not has_ors:
        pytest.skip("ORS_API_KEY not set")

    payload = {
        "adapter": "openrouteservice",
        "origins": [
            {"lat": 37.7749, "lon": -122.4194},
            {"lat": 34.0522, "lon": -118.2437},
        ],
        "destinations": [{"lat": 36.1699, "lon": -115.1398}],
        "mode": "driving",
    }
    r = client.post("/distance-matrix", json=payload)
    assert r.status_code == 200, r.text

    matrix = _matrix_from_response(r.json())
    assert "distances" in matrix
    assert len(matrix["distances"]) == 2 and len(matrix["distances"][0]) == 1
