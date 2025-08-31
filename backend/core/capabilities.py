from __future__ import annotations
from typing import Dict, List, Any
import os

_SOLVER_CAPS: Dict[str, Dict[str, Any]] = {
    "ortools": {
        "vrp_types": {
            "TSP": {
                "required": ["matrix.distances", "fleet>=1", "depot_index"],
                "optional": ["matrix.durations", "weights"],
            },
            "CVRP": {
                "required": ["matrix.distances", "fleet>=1", "demands", "depot_index"],
                "optional": ["matrix.durations", "node_service_times", "weights"],
            },
            "VRPTW": {
                "required": [
                    "matrix.durations",
                    "node_time_windows",
                    "fleet>=1",
                    "depot_index",
                ],
                "optional": ["matrix.distances", "node_service_times", "weights"],
            },
            "PDPTW": {
                "required": [
                    "matrix.durations",
                    "node_time_windows",
                    "pickup_delivery_pairs",
                    "demands",
                    "fleet>=1",
                    "depot_index",
                ],
                "optional": ["matrix.distances", "node_service_times", "weights"],
            },
        }
    },
    "pyomo": {
        "vrp_types": {
            "TSP": {
                "required": ["matrix.distances", "fleet>=1", "depot_index"],
                "optional": [],
            },
            "CVRP": {
                "required": ["matrix.distances", "fleet>=1", "demands", "depot_index"],
                "optional": [],
            },
            "VRPTW": {
                "required": [
                    "matrix.durations",
                    "node_time_windows",
                    "fleet>=1",
                    "depot_index",
                ],
                "optional": [],
            },
        }
    },
    "vroom": {
        "vrp_types": {
            "TSP": {
                "required": ["waypoints|matrix", "fleet==1", "depot_index"],
                "optional": ["weights"],
            }
        }
    },
    "mapbox_optimizer": {
        "vrp_types": {
            "TSP": {
                "required": ["waypoints", "fleet==1"],
                "optional": [
                    "roundtrip",
                    "depot_index",
                    "end_index",
                    "profile",
                    "annotations",
                    "radiuses",
                    "bearings",
                    "approaches",
                    "geometries",
                    "steps",
                ],
            },
            "PD": {
                "required": ["waypoints", "fleet==1", "pickup_delivery_pairs"],
                "optional": [
                    "roundtrip",
                    "depot_index",
                    "end_index",
                    "profile",
                    "annotations",
                    "radiuses",
                    "bearings",
                    "approaches",
                    "geometries",
                    "steps",
                ],
            },
        }
    },
}

_ADAPTER_CAPS: Dict[str, Dict[str, Any]] = {
    "haversine": {"provides": ["matrix.distances"]},
    "osm_graph": {"provides": ["matrix.distances", "matrix.durations"]},
    "openrouteservice": {"provides": ["matrix.distances", "matrix.durations"]},
    "google": {"provides": ["matrix.distances", "matrix.durations"]},
    "google_routes": {"provides": ["matrix.distances", "matrix.durations"]},
    "mapbox": {"provides": ["matrix.distances", "matrix.durations"]},
}


def _ensure_solver_registry_names() -> List[str]:
    try:
        from services.solver_factory import register_solvers, list_solvers

        register_solvers()  # idempotent
        names = list_solvers()
        if names:
            return names
    except Exception:
        pass
    return ["ortools", "pyomo", "vroom"]


def filter_registered(
    registered_solvers: List[str],
    registered_adapters: List[str],
) -> Dict[str, Any]:
    force_all = os.getenv("TEST_FORCE_ALL_SOLVERS") == "1"
    force_adapters = os.getenv("TEST_FORCE_ALL_ADAPTERS") == "1"

    if force_all:
        solvers_to_show = set(_SOLVER_CAPS.keys())
    else:
        solvers_to_show = set(registered_solvers) | set(_ensure_solver_registry_names())

    # auto-add mapbox optimizer if token or forced
    if os.getenv("MAPBOX_TOKEN") or force_all:
        solvers_to_show.add("mapbox_optimizer")

    solvers = []
    for name in sorted(solvers_to_show):
        caps = _SOLVER_CAPS.get(name)
        if caps:
            solvers.append({"name": name, **caps})

    if force_adapters:
        adapters_to_show = set(_ADAPTER_CAPS.keys())
    else:
        adapters_to_show = set(registered_adapters)

    adapters = []
    for name in sorted(adapters_to_show):
        caps = _ADAPTER_CAPS.get(name)
        if caps:
            adapters.append({"name": name, **caps})

    return {"solvers": solvers, "adapters": adapters}
