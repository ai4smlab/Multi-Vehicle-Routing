# backend/tests/test_solver_matrix_e2e_no_caps.py
from __future__ import annotations
import importlib
import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def _module_available(mod: str) -> bool:
    try:
        importlib.import_module(mod)
        return True
    except Exception:
        return False


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


# ---------------------------------------------------------
# Minimal 3-node instance (0=depot, 1..N-1=customers), km / s
# ---------------------------------------------------------
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


def _payload_tsp(solver: str):
    return {
        "solver": solver,
        "vrp_type": "TSP",
        "matrix": BASE_MATRIX,
        "fleet": BASE_FLEET,
        "depot_index": DEPOT,
        "weights": {"distance": 1.0, "time": 0.0},
    }


def _payload_cvrp(solver: str):
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


def _payload_vrptw(solver: str):
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


def _payload_pdptw(solver: str):
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


# ---------------------------------------------------------
# Param spaces (adapters are just labels for reporting)
# ---------------------------------------------------------
ADAPTERS = ["google", "mapbox", "openrouteservice", "osm_graph"]


@pytest.mark.parametrize("adapter", ADAPTERS, ids=lambda a: f"adapter={a}")
@pytest.mark.parametrize("vrp_type", ["TSP", "CVRP", "VRPTW", "PDPTW"])
def test_ortools_matrix_combos(vrp_type, adapter):
    # Skip only if OR-Tools module truly not importable
    if not _module_available("services.solvers.ortools_solver"):
        pytest.skip("ortools module not importable in this environment")

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


@pytest.mark.parametrize("adapter", ADAPTERS, ids=lambda a: f"adapter={a}")
@pytest.mark.parametrize("vrp_type", ["TSP", "CVRP", "VRPTW"])
def test_pyomo_matrix_combos(vrp_type, adapter):
    # Skip only if Pyomo solver module not importable (e.g., missing pyomo/CBC)
    if not _module_available("services.solvers.pyomo_solver"):
        pytest.skip("pyomo solver module not importable in this environment")

    if vrp_type == "TSP":
        payload = _payload_tsp("pyomo")
    elif vrp_type == "CVRP":
        payload = _payload_cvrp("pyomo")
    else:
        payload = _payload_vrptw("pyomo")

    r = client.post("/solver", json=payload)
    _assert_ok(r)
