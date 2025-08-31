# core/logic/constraints.py
from __future__ import annotations
from typing import Any, Dict, List, Optional


def check_matrix_square(distances: List[List[float]]) -> Optional[str]:
    n = len(distances)
    if n == 0:
        return "distance matrix is empty"
    if any(len(row) != n for row in distances):
        return "distance matrix must be square"
    return None


def check_demands_length(demands: Optional[List[int]], n: int) -> Optional[str]:
    if demands is None:
        return None
    if len(demands) != n:
        return f"demands length {len(demands)} != matrix size {n}"
    return None


def check_time_windows_length(
    tw: Optional[List[Optional[List[int]]]], n: int
) -> Optional[str]:
    if tw is None:
        return None
    if len(tw) != n:
        return f"node_time_windows length {len(tw)} != matrix size {n}"
    # verify shape
    for i, win in enumerate(tw):
        if win is None:
            continue
        if not (isinstance(win, (list, tuple)) and len(win) == 2):
            return f"time window at node {i} is not [start,end]"
        if int(win[0]) > int(win[1]):
            return f"time window at node {i} has start>end"
    return None


def check_service_times_length(service: Optional[List[int]], n: int) -> Optional[str]:
    if service is None:
        return None
    if len(service) != n:
        return f"node_service_times length {len(service)} != matrix size {n}"
    return None


def check_capacity_feasibility(
    demands: Optional[List[int]], vehicle_caps: List[int]
) -> Optional[str]:
    if demands is None:
        return None
    if sum(max(0, int(d)) for d in demands) > sum(int(c) for c in vehicle_caps):
        return "total demand exceeds total fleet capacity"
    return None


def validate_instance(instance: Dict[str, Any]) -> List[str]:
    """Return a list of human-readable issues (empty if OK)."""
    issues: List[str] = []
    matrix = instance.get("matrix") or {}
    distances = matrix.get("distances") or []
    n = len(distances) if distances else 0

    # matrix shape
    msg = check_matrix_square(distances) if distances else "missing matrix.distances"
    if msg:
        issues.append(msg)

    # lengths
    issues += [
        x
        for x in (
            check_demands_length(instance.get("demands"), n),
            check_time_windows_length(instance.get("node_time_windows"), n),
            check_service_times_length(instance.get("node_service_times"), n),
        )
        if x
    ]

    # capacity sanity
    fleet = instance.get("fleet") or {}
    vehicles = list(fleet.get("vehicles", []))
    caps = (
        [int((v.get("capacity") or [10**9])[0]) for v in vehicles]
        if vehicles
        else [10**9]
    )
    cap_msg = check_capacity_feasibility(instance.get("demands"), caps)
    if cap_msg:
        issues.append(cap_msg)

    return issues
