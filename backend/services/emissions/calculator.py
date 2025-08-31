from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Leg:
    distance_km: float
    duration_s: Optional[float]
    vehicle_type: str
    fuel: str
    scope: str = "TTW"  # or "WTW"


def emissions_for_leg(leg: Leg, factors) -> float:
    speed_kmh = None
    if leg.duration_s and leg.duration_s > 0:
        speed_kmh = leg.distance_km / (leg.duration_s / 3600.0)

    if speed_kmh is not None and factors.has_speed_bins(
        leg.vehicle_type, leg.fuel, leg.scope
    ):
        ef = factors.by_speed(leg.vehicle_type, leg.fuel, leg.scope, speed_kmh)  # g/km
    else:
        ef = factors.per_km(leg.vehicle_type, leg.fuel, leg.scope)  # g/km
    return leg.distance_km * ef / 1000.0  # => kg CO2e


def route_emissions(legs: List[Leg], factors) -> float:
    return sum(emissions_for_leg(l, factors) for l in legs)
