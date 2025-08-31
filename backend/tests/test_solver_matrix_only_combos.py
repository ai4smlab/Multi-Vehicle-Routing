# backend/tests/test_solver_matrix_only_combos.py
from __future__ import annotations
import pytest
from typing import Dict, Any

# NOTE: client fixture is defined in conftest.py (ensures lifespan + registration)


def _capabilities(client) -> Dict[str, Any]:
    r = client.get("/capabilities")
    assert r.status_code == 200, r.text
    return r.json()


def _solver_available(client, name: str) -> bool:
    caps = _capabilities(client)
    return any(s["name"] == name for s in caps.get("solvers", []))


# --- Tiny 3-node instance (0=depot, 1..N-1=customers), km / s ---
BASE_MATRIX = {
    "distances": [
        [0.0, 1.0, 1.5],
        [1.0, 0.0, 1.2],
        [1.5, 1.2, 0.0],
    ],
    "durations": [
        [0, 600, 900],
        [600, 0, 720],
        [900, 720, 0],
    ],
}
BASE_FLEET = [{"id": "veh-1", "start": 0, "end": 0, "capacity": [10]}]
DEPOT = 0


def _payload_tsp(solver: str) -> Dict[str, Any]:
    return {
        "solver": solver,
        "vrp_type": "TSP",
        "matrix": BASE_MATRIX,
        "fleet": BASE_FLEET,
        "depot_index": DEPOT,
        "weights": {"distance": 1.0, "time": 0.0},
    }


def _payload_cvrp(solver: str) -> Dict[str, Any]:
    return {
        "solver": solver,
        "vrp_type": "CVRP",
        "matrix": BASE_MATRIX,
        "fleet": BASE_FLEET,
        "depot_index": DEPOT,
        "demands": [0, 5, 3],
        "node_service_times": [0, 60, 60],
        "weights": {"distance": 1.0, "time": 0.0},
    }


def _payload_vrptw(solver: str) -> Dict[str, Any]:
    return {
        "solver": solver,
        "vrp_type": "VRPTW",
        "matrix": BASE_MATRIX,
        "fleet": BASE_FLEET,
        "depot_index": DEPOT,
        "node_time_windows": [
            [0, 7200],  # depot
            [0, 7200],
            [0, 7200],
        ],
        "node_service_times": [0, 120, 120],
        "weights": {"distance": 0.0, "time": 1.0},
    }


def _payload_pdptw(solver: str) -> Dict[str, Any]:
    return {
        "solver": solver,
        "vrp_type": "PDPTW",
        "matrix": BASE_MATRIX,
        "fleet": BASE_FLEET,
        "depot_index": DEPOT,
        "demands": [0, 5, -5],
        "pickup_delivery_pairs": [{"pickup": 1, "delivery": 2}],
        "node_time_windows": [
            [0, 7200],  # depot
            [0, 7200],  # pickup
            [0, 7200],  # delivery
        ],
        "node_service_times": [0, 60, 60],
        "weights": {"distance": 0.5, "time": 0.5},
    }


def _assert_ok(resp):
    assert resp.status_code == 200, resp.text
    j = resp.json()
    status_top = j.get("status")
    status_inner = (j.get("data") or {}).get("status")
    assert status_top in ("success", "ok", "OK") or status_inner in (
        "success",
        "ok",
        "OK",
    ), j
    data = j.get("data") or {}
    routes = data.get("routes") or []
    assert isinstance(routes, list) and len(routes) >= 1, f"no routes in response: {j}"
    r0 = routes[0]
    assert "vehicle_id" in r0
    assert isinstance(r0.get("waypoint_ids", []), list) and len(r0["waypoint_ids"]) >= 2


# -------------------------------
# Param spaces (adapters are labels only for reporting)
# -------------------------------
ORTOOLS_ADAPTERS = ["google", "mapbox", "openrouteservice", "osm_graph"]
PYOMO_ADAPTERS = ["google", "mapbox", "openrouteservice", "osm_graph"]


@pytest.mark.parametrize("adapter", ORTOOLS_ADAPTERS, ids=lambda a: f"adapter={a}")
@pytest.mark.parametrize("vrp_type", ["TSP", "CVRP", "VRPTW", "PDPTW"])
def test_ortools_with_matrix_combos(client, vrp_type, adapter):
    if not _solver_available(client, "ortools"):
        pytest.skip("ortools solver not available in /capabilities")
    if vrp_type == "TSP":
        payload = _payload_tsp("ortools")
    elif vrp_type == "CVRP":
        payload = _payload_cvrp("ortools")
    elif vrp_type == "VRPTW":
        payload = _payload_vrptw("ortools")
    else:
        payload = _payload_pdptw("ortools")

    r = client.post("/solver", json=payload)
    _assert_ok(r)


@pytest.mark.parametrize("adapter", PYOMO_ADAPTERS, ids=lambda a: f"adapter={a}")
@pytest.mark.parametrize("vrp_type", ["TSP", "CVRP", "VRPTW"])
def test_pyomo_with_matrix_combos(client, vrp_type, adapter):
    if not _solver_available(client, "pyomo"):
        pytest.skip(
            "pyomo solver not available in /capabilities (CBC/pyomo not present?)"
        )
    if vrp_type == "TSP":
        payload = _payload_tsp("pyomo")
    elif vrp_type == "CVRP":
        payload = _payload_cvrp("pyomo")
    else:
        payload = _payload_vrptw("pyomo")

    r = client.post("/solver", json=payload)
    _assert_ok(r)
