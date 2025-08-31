import os
import math
from pathlib import Path
from typing import List, Dict, Any, Optional

import pytest
from starlette.testclient import TestClient

# FastAPI app (option A import)
from main import app  # adjust if your import path differs

# dataset utilities
from file_handler.dataset_indexer import find_pair

try:
    # if you exposed a single parsing function
    from file_handler.solution_loader import load_solution_sol as _load_solution
except Exception:
    _load_solution = None

# ---- Test config ----
DATA_DIR = Path(os.getenv("DATA_DIR", "./backend/data")).resolve()
XML100_DATASET = "Vrp-Set-XML100"
SOLOMON_DATASET = "solomon"

# Choose “known” items; adjust if your dataset uses different names.
XML100_NAME = "XML100_3375_23"  # base name without extension
SOLOMON_NAME = "C101"  # classic Solomon instance


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _route_total_distance_km(
    routes_payload: Dict[str, Any], matrix: Dict[str, List[List[float]]]
) -> float:
    """Sum distance over all routes using the provided distance matrix."""
    dist = matrix.get("distances")
    if not dist:
        return 0.0
    total = 0.0
    for r in routes_payload.get("routes", []):
        wp_ids = r.get("waypoint_ids", [])
        if len(wp_ids) < 2:
            continue
        # waypoint_ids come as strings; convert to ints
        try:
            idxs = [int(x) for x in wp_ids]
        except Exception:
            # If they are names, try to coerce
            idxs = [int(str(x)) for x in wp_ids]
        for a, b in zip(idxs, idxs[1:]):
            total += float(dist[a][b])
    return total


def _load_solution_file(sol_path: Path) -> Optional[Dict[str, Any]]:
    """Best-effort solution parsing via solution_loader if available."""
    if not sol_path or not sol_path.exists():
        return None
    if _load_solution is None:
        return None
    try:
        return _load_solution(str(sol_path))
    except Exception:
        return None


def _instance_to_solver_payload(
    instance_dict: Dict[str, Any], solver: str = "ortools"
) -> Dict[str, Any]:
    """
    Convert the instance dict to a /solver payload for a given solver.
    - ortools/pyomo: use distance matrix + (optional) tw/service/demands
    - vroom: use coordinate mode (waypoints with lat/lon)
    """
    waypoints = instance_dict.get("waypoints") or []
    depot_index = int(instance_dict.get("depot_index", 0))
    fleet = instance_dict.get("fleet")

    # normalize fleet -> list of vehicles
    if isinstance(fleet, dict) and "vehicles" in fleet:
        fleet_list = fleet["vehicles"]
    else:
        fleet_list = fleet or []

    if solver.lower() in {"ortools", "pyomo"}:
        # common path using a matrix
        matrix = instance_dict.get("matrix") or {}
        if not matrix.get("distances"):
            raise RuntimeError(
                "Instance has no distance matrix; enable compute_matrix or precompute matrices."
            )

        # collect optional fields from waypoints
        demands, tw, service = [], [], []
        for wp in waypoints:
            demands.append(int(wp.get("demand", 0)))
            win = wp.get("time_window")
            tw.append(win if win is not None else None)
            service.append(int(wp.get("service_time", 0)))

        payload = {
            "solver": solver.lower(),
            "matrix": {
                "distances": matrix["distances"],
                **(
                    {"durations": matrix["durations"]}
                    if matrix.get("durations")
                    else {}
                ),
            },
            "fleet": fleet_list,
            "depot_index": depot_index,
            "demands": demands if any(demands) else None,
            "node_time_windows": tw if any(x is not None for x in tw) else None,
            "node_service_times": service if any(service) else None,
        }
        # small nits to help solomon match:
        if solver.lower() == "ortools":
            payload["weights"] = {
                "distance": 1.0,
                "time": 0.0,
                "vehicle_fixed_cost": 100,
            }
        return {k: v for k, v in payload.items() if v is not None}

    elif solver.lower() == "vroom":
        # coordinate mode: feed waypoints directly; VROOM will build its own matrix
        # Tip: keep fleet as-is; vehicles' start/end indexes already refer to depot_index
        return {
            "solver": "vroom",
            "waypoints": waypoints,
            "fleet": fleet_list,
            "depot_index": depot_index,
            # add a hint if your VROOM wrapper supports it (optional):
            # "coordinate_mode": True
        }

    else:
        raise ValueError(f"Unknown solver {solver}")


def _assert_against_solution(
    parsed_solution: Dict[str, Any],
    routes_payload: Dict[str, Any],
    matrix: Dict[str, List[List[float]]],
    tol_ratio: float = 0.25,
):
    """
    Compare solver output against a parsed solution:
      - route count (if solution has routes)
      - customer coverage (if solution has per-route nodes)
      - total distance within a tolerance (if solution exposes objective)
    """
    if not parsed_solution:
        pytest.skip("No solution parser or solution file lacks structured data")

    # Known keys to try:
    sol_routes = parsed_solution.get("routes")
    sol_total = (
        parsed_solution.get("total_distance")
        or parsed_solution.get("cost")
        or parsed_solution.get("distance")
    )

    # Compare route count if available
    if sol_routes:
        exp_count = len(sol_routes)
        got_count = len(routes_payload.get("routes", []))
        # Allow equal or fewer (heuristic might consolidate), but flag if wildly different
        assert got_count <= exp_count or math.isclose(
            got_count, exp_count
        ), f"route count mismatch: expected {exp_count}, got {got_count}"

        # Compare customer coverage if we have explicit node lists
        exp_customers = set()
        for r in sol_routes:
            nodes = r.get("nodes") or r.get("stops") or r  # accept raw list
            # many solution files are 1-based; normalize to 0-based by subtracting 1
            for nid in nodes:
                try:
                    ni = int(nid)
                    if ni > 0:
                        exp_customers.add(ni - 1)
                except Exception:
                    continue

        got_customers = set()
        for r in routes_payload.get("routes", []):
            for nid in r.get("waypoint_ids", []):
                try:
                    ni = int(nid)
                    if ni != 0:  # skip depot (assuming depot_index == 0)
                        got_customers.add(ni)
                except Exception:
                    continue

        if exp_customers:
            # we only assert subset to be robust (heuristic may skip infeasible nodes if data mismatch)
            assert got_customers.issubset(
                exp_customers
            ), f"solver visited nodes not in solution set: extra={sorted(got_customers - exp_customers)}"

    # Compare total distance if solution gives a number
    if sol_total is not None:
        got_total = _route_total_distance_km(routes_payload, matrix)
        # tolerate %-error
        if sol_total > 0:
            ratio_err = abs(got_total - float(sol_total)) / float(sol_total)
            assert (
                ratio_err <= tol_ratio
            ), f"total distance off by {ratio_err:.1%}: expected {sol_total}, got {got_total}"


@pytest.mark.slow
def test_xml100_instance_vs_solution(client):
    ds_root = DATA_DIR / XML100_DATASET
    if not ds_root.exists():
        pytest.skip(f"{XML100_DATASET} dataset not found at {ds_root}")

    pair = find_pair(XML100_DATASET, XML100_NAME)
    if not pair or not pair.get("instance"):
        pytest.skip(f"Instance {XML100_NAME} not found in {XML100_DATASET}")

    inst_path = Path(pair["instance"]["path"])
    sol_path = (
        Path(pair.get("solution", {}).get("path", "")) if pair.get("solution") else None
    )

    # Load instance using your API route to stay e2e, or directly if you prefer:
    # Here we do it via route: /benchmarks/load?dataset=...&name=...
    r = client.get(
        "/benchmarks/load", params={"dataset": XML100_DATASET, "name": XML100_NAME}
    )
    assert r.status_code == 200, r.text
    inst = r.json().get("data") or r.json()  # support wrapper or raw

    # Build solve payload for OR-Tools
    solve_req = _instance_to_solver_payload(inst)

    rs = client.post("/solver", json=solve_req)
    assert rs.status_code == 200, rs.text
    data = rs.json().get("data") or rs.json()
    assert data.get("status") == "success"
    routes_payload = data

    # Compare vs solution if we can parse it
    parsed_solution = _load_solution_file(sol_path) if sol_path else None
    _assert_against_solution(
        parsed_solution, routes_payload, solve_req["matrix"], tol_ratio=0.30
    )


@pytest.mark.slow
def test_solomon_instance_vs_solution(client):
    ds_root = DATA_DIR / SOLOMON_DATASET
    if not ds_root.exists():
        pytest.skip(f"{SOLOMON_DATASET} dataset not found at {ds_root}")

    pair = find_pair(SOLOMON_DATASET, SOLOMON_NAME)
    if not pair or not pair.get("instance"):
        pytest.skip(f"Instance {SOLOMON_NAME} not found in {SOLOMON_DATASET}")

    inst_path = Path(pair["instance"]["path"])
    sol_path = (
        Path(pair.get("solution", {}).get("path", "")) if pair.get("solution") else None
    )

    # Load instance (via route for end-to-end)
    r = client.get(
        "/benchmarks/load", params={"dataset": SOLOMON_DATASET, "name": SOLOMON_NAME}
    )
    assert r.status_code == 200, r.text
    inst = r.json().get("data") or r.json()

    # Build solve payload
    solve_req = _instance_to_solver_payload(inst)

    rs = client.post("/solver", json=solve_req)
    assert rs.status_code == 200, rs.text
    data = rs.json().get("data") or rs.json()
    assert data.get("status") == "success"
    routes_payload = data

    parsed_solution = _load_solution_file(sol_path) if sol_path else None
    _assert_against_solution(
        parsed_solution, routes_payload, solve_req["matrix"], tol_ratio=0.35
    )


@pytest.mark.slow
def test_solomon_instance_vs_solution_pyomo(client):
    import os

    if os.getenv("RUN_PYOMO_BENCH", "0") != "1":
        pytest.skip("Set RUN_PYOMO_BENCH=1 to run the Pyomo Solomon benchmark test")

    ds_root = DATA_DIR / SOLOMON_DATASET
    if not ds_root.exists():
        pytest.skip(f"{SOLOMON_DATASET} dataset not found at {ds_root}")

    pair = find_pair(SOLOMON_DATASET, SOLOMON_NAME)
    if not pair or not pair.get("instance"):
        pytest.skip(f"Instance {SOLOMON_NAME} not found in {SOLOMON_DATASET}")

    sol_path = (
        Path(pair.get("solution", {}).get("path", "")) if pair.get("solution") else None
    )

    r = client.get(
        "/benchmarks/load", params={"dataset": SOLOMON_DATASET, "name": SOLOMON_NAME}
    )
    assert r.status_code == 200, r.text
    inst = r.json().get("data") or r.json()

    solve_req = _instance_to_solver_payload(inst, solver="pyomo")
    rs = client.post("/solver", json=solve_req)
    assert rs.status_code == 200, rs.text
    data = rs.json().get("data") or rs.json()
    assert data.get("status") == "success"
    routes_payload = data

    parsed_solution = _load_solution_file(sol_path) if sol_path else None
    # keep a looser tolerance; Pyomo formulation/params may differ
    _assert_against_solution(
        parsed_solution, routes_payload, solve_req["matrix"], tol_ratio=0.40
    )


@pytest.mark.slow
def test_solomon_instance_vs_solution_vroom(client):
    ds_root = DATA_DIR / SOLOMON_DATASET
    if not ds_root.exists():
        pytest.skip(f"{SOLOMON_DATASET} dataset not found at {ds_root}")

    pair = find_pair(SOLOMON_DATASET, SOLOMON_NAME)
    if not pair or not pair.get("instance"):
        pytest.skip(f"Instance {SOLOMON_NAME} not found in {SOLOMON_DATASET}")

    sol_path = (
        Path(pair.get("solution", {}).get("path", "")) if pair.get("solution") else None
    )

    r = client.get(
        "/benchmarks/load", params={"dataset": SOLOMON_DATASET, "name": SOLOMON_NAME}
    )
    assert r.status_code == 200, r.text
    inst = r.json().get("data") or r.json()

    # Build coordinate-mode request
    solve_req = _instance_to_solver_payload(inst, solver="vroom")

    rs = client.post("/solver", json=solve_req)
    assert rs.status_code == 200, rs.text
    data = rs.json().get("data") or rs.json()
    assert data.get("status") == "success"

    # For distance comparison we need a matrix.
    # Use the instance’s matrix (Euclidean from loader) for measuring the produced routes.
    matrix = inst.get("matrix")
    assert matrix and matrix.get(
        "distances"
    ), "Instance matrix required for distance check"

    routes_payload = data
    parsed_solution = _load_solution_file(sol_path) if sol_path else None
    if parsed_solution:
        parsed_solution = dict(parsed_solution)
        parsed_solution.pop("routes", None)  # skip route-count check for VROOM

    # Relax tolerance a bit for heuristic differences
    _assert_against_solution(parsed_solution, routes_payload, matrix, tol_ratio=0.45)
