# services/solvers/common.py
from typing import List, Optional
from models.distance_matrix import MatrixResult


def sum_distance(route_nodes: List[int], matrix: MatrixResult) -> Optional[float]:
    if not matrix.distances:
        return None
    dist = 0.0
    for i in range(len(route_nodes) - 1):
        a, b = route_nodes[i], route_nodes[i + 1]
        dist += matrix.distances[a][b]
    # distances are expected in km (ensure upstream adapters return km)
    return dist


def sum_duration(route_nodes: List[int], matrix: MatrixResult) -> Optional[int]:
    if not matrix.durations:
        return None
    secs = 0.0
    for i in range(len(route_nodes) - 1):
        a, b = route_nodes[i], route_nodes[i + 1]
        secs += matrix.durations[a][b]
    return int(secs)


def estimate_emissions_kgs(
    distance_km: Optional[float], g_per_km: Optional[float]
) -> Optional[float]:
    if distance_km is None or g_per_km is None:
        return None
    return round((distance_km * g_per_km) / 1000.0, 6)
