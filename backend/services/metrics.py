# services/metrics.py
from typing import Optional, List
from models.distance_matrix import MatrixResult
from models.fleet import Vehicle
from models.solvers import Routes


def enrich_routes_with_metrics(
    routes: Routes,
    matrix: MatrixResult,
    fleet: List[Vehicle],
    depot_index: int = 0,
    cost_weight_km: float = 1.0,
) -> Routes:
    # compute distance/duration per route, then cost & emissions
    for r in routes.routes:
        # waypoint ids are strings; convert to ints
        idxs = [int(x) for x in r.waypoint_ids]
        dist = 0.0
        dur: Optional[float] = None
        if matrix.durations is not None:
            dur = 0.0
        for i in range(len(idxs) - 1):
            a, b = idxs[i], idxs[i + 1]
            dist += float(matrix.distances[a][b])  # assume KM
            if dur is not None:
                dur += float(matrix.durations[a][b])  # seconds

        r.total_distance = dist
        r.total_duration = int(dur) if dur is not None else None

        # cost/emissions using matching vehicle
        v = next((v for v in fleet if v.id == r.vehicle_id), None)
        if v:
            km = dist
            r.metadata = r.metadata or {}
            if getattr(v, "cost_per_km", None) is not None:
                r.metadata["cost"] = km * float(v.cost_per_km)
            if getattr(v, "emissions_per_km", None) is not None:
                r.emissions = km * float(v.emissions_per_km)
    return routes
