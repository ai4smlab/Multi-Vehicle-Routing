# core/emissions.py
from __future__ import annotations
from typing import Optional, List, Dict
from models.emissions import EmissionFactors, EmissionsResult


def estimate_emissions(
    distance_km: float,
    fuel_type: Optional[str] = None,
    vehicle_factor_kg_per_km: Optional[float] = None,
    defaults: Optional[EmissionFactors] = None,
) -> EmissionsResult:
    ef = (defaults or EmissionFactors()).factor_for(fuel_type, vehicle_factor_kg_per_km)
    kg = float(distance_km) * ef
    return EmissionsResult(kg_co2e=kg, g_co2e=int(round(kg * 1000)))


def estimate_route_from_path(
    path: List[int],
    matrix: Dict[str, List[List[float]]],
    fuel_type: Optional[str] = None,
    vehicle_factor_kg_per_km: Optional[float] = None,
    defaults: Optional[EmissionFactors] = None,
) -> EmissionsResult:
    """Compute distance from matrix + path, then emissions."""
    dmat = matrix.get("distances") or []
    dist_km = 0.0
    for a, b in zip(path, path[1:]):
        dist_km += float(dmat[a][b])
    return estimate_emissions(dist_km, fuel_type, vehicle_factor_kg_per_km, defaults)
