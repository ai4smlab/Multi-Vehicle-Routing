from typing import List, Optional
from pydantic import BaseModel


class Vehicle(BaseModel):
    id: str
    capacity: Optional[List[int]] = None  # Multiple dimensions (weight, volume, etc.)
    skills: Optional[List[str]] = None  # For skill-based routing
    start: Optional[int] = None  # Index in waypoints
    end: Optional[int] = None  # Index in waypoints
    time_window: Optional[List[int]] = None  # [start_time, end_time]
    max_distance: Optional[float] = None
    max_duration: Optional[float] = None
    speed: Optional[float] = None  # useful for simulation
    emissions_per_km: Optional[float] = None  # for eco-VRP


class FleetConfig(BaseModel):
    vehicles: List[Vehicle]
    capacity: Optional[int] = None


class Fleet(BaseModel):
    vehicles: List[Vehicle]
