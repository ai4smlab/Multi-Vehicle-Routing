# core/logic/cost_functions.py
from __future__ import annotations
from typing import Dict, List, Optional

DEFAULT_WEIGHTS: Dict[str, float] = {"distance": 1.0, "time": 0.0}


def arc_cost(
    distance_km: float,
    duration_sec: Optional[float] = None,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    time_hr = (duration_sec or 0.0) / 3600.0
    return w["distance"] * float(distance_km) + w["time"] * float(time_hr)


def route_cost(
    path: List[int],
    matrix: Dict[str, List[List[float]]],
    weights: Optional[Dict[str, float]] = None,
) -> float:
    dmat = matrix.get("distances") or []
    tmat = matrix.get("durations")
    total = 0.0
    for a, b in zip(path, path[1:]):
        dist = float(dmat[a][b])
        dur = float(tmat[a][b]) if tmat is not None else None
        total += arc_cost(dist, dur, weights)
    return total
