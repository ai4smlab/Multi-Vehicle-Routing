from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator, field_validator


class Location(BaseModel):
    lat: float
    lon: float


class TimeWindow(BaseModel):
    start: int  # seconds from midnight
    end: int  # seconds from midnight


class Waypoint(BaseModel):
    id: str
    location: Location
    type: Optional[str] = Field(default="customer")
    demand: Optional[List[int]] = None
    service_duration: Optional[int] = 0
    time_window: Optional[TimeWindow] = None
    skills_required: Optional[List[str]] = None
    pickup_delivery_id: Optional[str] = None
    paired_with: Optional[str] = None
    priority: Optional[int] = 1
    emissions: Optional[float] = None

    # Accept demand = int -> [int] also for nested shape
    @field_validator("demand", mode="before")
    @classmethod
    def _coerce_demand_list(cls, v):
        if v is None:
            return None
        if isinstance(v, list):
            return [int(x) for x in v]
        # accept int/float/str "3"
        try:
            return [int(float(v))]
        except Exception:
            return v  # let pydantic report if it still doesn't fit

    # Accept and convert the existing "flat" schema automatically:
    @model_validator(mode="before")
    @classmethod
    def _accept_flat_shape(cls, v: Any) -> Any:
        if not isinstance(v, dict):
            return v

        # If already nested, do nothing
        if "location" in v:
            return v

        # Detect flat shape with lat/lon
        if "lat" in v and "lon" in v:
            out: Dict[str, Any] = dict(v)  # shallow copy

            # location
            out["location"] = {"lat": float(v["lat"]), "lon": float(v["lon"])}
            out.pop("lat", None)
            out.pop("lon", None)

            # demand: allow int -> [int]
            if "demand" in v and not isinstance(v["demand"], list):
                d = v.get("demand", 0)
                out["demand"] = [int(d)]

            # service_time -> service_duration
            if "service_time" in v and "service_duration" not in v:
                out["service_duration"] = int(v.get("service_time") or 0)
                out.pop("service_time", None)

            # time_window: [start, end] -> TimeWindow
            if (
                "time_window" in v
                and isinstance(v["time_window"], (list, tuple))
                and len(v["time_window"]) == 2
            ):
                start, end = v["time_window"]
                out["time_window"] = {"start": int(start), "end": int(end)}

            # skills -> skills_required
            if "skills" in v and "skills_required" not in v:
                out["skills_required"] = v["skills"]
                out.pop("skills", None)

            # depot flag -> type
            if v.get("depot") is True:
                out["type"] = "depot"
                out.pop("depot", None)
            else:
                # remove 'depot' if present (not needed)
                out.pop("depot", None)

            return out

        return v


class WaypointsRequest(BaseModel):
    waypoints: List[Waypoint]
