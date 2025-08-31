# models/mapbox_models.py
from __future__ import annotations
from typing import List, Optional, Literal, Any
from pydantic import BaseModel, Field


# ---- requests ----
class MapboxCoord(BaseModel):
    lon: float
    lat: float


class MapboxMatrixRequest(BaseModel):
    profile: Literal["driving", "walking", "cycling"] = "driving"
    coordinates: List[MapboxCoord]
    annotations: List[Literal["distance", "duration"]] = Field(
        default_factory=lambda: ["distance", "duration"]
    )


class MapboxOptimizeRequest(BaseModel):
    profile: Literal["driving", "walking", "cycling"] = "driving"
    coordinates: List[MapboxCoord]
    roundtrip: bool = True
    source: Literal["any", "first"] = "first"
    destination: Literal["any", "last"] = "last"


class MapboxMatchRequest(BaseModel):
    profile: Literal["driving", "walking", "cycling"] = "driving"
    coordinates: List[MapboxCoord]


# ---- responses (keep permissive to avoid 500s in tests) ----
class MapboxMatrixResponse(BaseModel):
    code: Optional[str] = None
    distances: Optional[List[List[float]]] = None
    durations: Optional[List[List[float]]] = None
    # accept anything else Mapbox may return
    # (e.g., "sources", "destinations", "units", etc.)
    # Pydantic will ignore extra keys by default


class MapboxOptimizeResponse(BaseModel):
    code: Optional[str] = None
    trips: Optional[List[Any]] = None
    waypoints: Optional[List[Any]] = None


class MapboxMatchResponse(BaseModel):
    code: Optional[str] = None
    matchings: Optional[List[Any]] = None
