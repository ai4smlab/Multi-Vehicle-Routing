# file_handler/vrplib_lib_wrapper.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional
import math

try:
    import vrplib as _vrplib

    VRPLIB_AVAILABLE = True
except Exception:
    VRPLIB_AVAILABLE = False


def _euclid_mtx(coords: List[tuple[float, float]]) -> List[List[float]]:
    n = len(coords)
    mtx = [[0.0] * n for _ in range(n)]
    for i in range(n):
        xi, yi = coords[i]
        for j in range(i + 1, n):
            xj, yj = coords[j]
            d = math.hypot(xi - xj, yi - yj)
            mtx[i][j] = d
            mtx[j][i] = d
    return mtx


def load_with_vrplib(path: str | Path, compute_matrix: bool = True) -> Dict[str, Any]:
    if not VRPLIB_AVAILABLE:
        raise RuntimeError("vrplib not installed")

    inst = _vrplib.read_instance(str(path))

    coords = inst.get("coordinates") or inst.get("node_coords")
    edge_mtx = inst.get("edge_weight")
    edge_type = (inst.get("edge_weight_type") or "EUC_2D").upper()

    if coords is None and edge_mtx is None:
        raise ValueError(
            "vrplib: instance has neither coordinates nor edge_weight matrix"
        )

    n = len(coords) if coords is not None else len(edge_mtx)
    if n is None or n <= 0:
        raise ValueError("vrplib: could not derive node count")

    depot = inst.get("depot", 1)
    if isinstance(depot, (list, tuple)):
        depot_index = int(depot[0]) - 1
    else:
        depot_index = int(depot) - 1
    depot_index = max(0, min(depot_index, n - 1))

    demands = inst.get("demands") or [0] * n
    if len(demands) < n:
        demands = list(demands) + [0] * (n - len(demands))
    demands = [int(x or 0) for x in demands[:n]]

    def _as_list(v, fill=0):
        if v is None:
            return [fill] * n
        vv = list(v)
        if len(vv) < n:
            vv = vv + [fill] * (n - len(vv))
        return vv[:n]

    ready = _as_list(inst.get("ready_time"), 0)
    due = _as_list(inst.get("due_time"), 10**9)
    service = _as_list(inst.get("service_time"), 0)

    for i in range(n):
        if due[i] < ready[i]:
            ready[i], due[i] = due[i], ready[i]

    max_due = max(due) if due else 10**9
    ready[depot_index] = min(ready[depot_index], 0)
    due[depot_index] = max(due[depot_index], max_due)

    waypoints: List[Dict[str, Any]] = []
    if coords is not None:
        for i, (x, y) in enumerate(coords, start=1):
            waypoints.append(
                {
                    "id": str(i),
                    # keep both spaces (solver x,y + legacy planar lat/lon)
                    "x": float(x),
                    "y": float(y),
                    "lat": float(x),
                    "lon": float(y),
                    "demand": int(demands[i - 1] if i - 1 < len(demands) else 0),
                    "service_time": int(service[i - 1]),
                    "time_window": [int(ready[i - 1]), int(due[i - 1])],
                    "depot": (i - 1) == depot_index,
                }
            )
    else:
        for i in range(n):
            waypoints.append(
                {
                    "id": str(i + 1),
                    "x": float(i),
                    "y": 0.0,
                    "lat": float(i),
                    "lon": 0.0,
                    "demand": int(demands[i]),
                    "service_time": int(service[i]),
                    "time_window": [int(ready[i]), int(due[i])],
                    "depot": i == depot_index,
                }
            )

    veh_count = (
        inst.get("vehicles")
        or inst.get("num_vehicles")
        or inst.get("vehicle_number")
        or inst.get("nb_vehicles")
        or inst.get("vehicle_num")
        or inst.get("number_vehicles")
        or inst.get("number")
        or inst.get("vehicle")
        or 1
    )
    try:
        veh_count = int(veh_count)
    except Exception:
        veh_count = 1

    pstr = str(path).lower()
    if (
        veh_count <= 1
        and pstr.endswith(".txt")
        and ("solomon" in pstr or "/solomon/" in pstr)
    ):
        veh_count = 25

    cap = int(inst.get("capacity", 10**9))

    total_demand = sum(int(max(0, d)) for d in demands)
    if cap > 0:
        needed = max(1, math.ceil(total_demand / cap))
        veh_count = max(veh_count, min(needed, n))
    else:
        veh_count = max(veh_count, 1)

    vehicles = [
        {
            "id": f"veh-{i+1}",
            "start": depot_index,
            "end": depot_index,
            "capacity": [cap],
            "skills": [],
            "time_window": None,
            "max_distance": None,
            "max_duration": None,
            "speed": None,
            "emissions_per_km": None,
        }
        for i in range(veh_count)
    ]

    distances: Optional[List[List[float]]] = None
    if edge_mtx is not None:
        distances = [[float(x) for x in row] for row in edge_mtx]
    elif compute_matrix and coords is not None:
        distances = _euclid_mtx([(float(x), float(y)) for (x, y) in coords])

    matrix = None
    if distances is not None:
        is_solomon_txt = pstr.endswith(".txt") and (
            "solomon" in pstr or "/solomon/" in pstr
        )
        durations = (
            [[int(round(d * 60)) for d in row] for row in distances]
            if is_solomon_txt
            else [[d for d in row] for row in distances]
        )
        matrix = {"distances": distances, "durations": durations}

    return {
        "edge_weight_type": edge_type,
        "coordinate_spaces": {
            "solver": (
                {"type": "euclidean", "fields": ["x", "y"]}
                if edge_type.startswith("EUC")
                else {"type": "wgs84", "fields": ["lon", "lat"]}
            ),
            "display": {"type": "wgs84", "fields": ["lon", "lat"]},
        },
        "waypoints": waypoints,
        "fleet": {"vehicles": vehicles},
        "depot_index": depot_index,
        "matrix": matrix,
        "meta": {
            "source": str(path),
            "format": "vrplib",
            "capacity": cap,
        },
    }
