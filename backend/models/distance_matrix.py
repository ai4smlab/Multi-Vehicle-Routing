from typing import List, Dict, Optional, Any
from pydantic import BaseModel, root_validator, validator


class Coordinate(BaseModel):
    lat: float
    lon: float


def _coerce_coords(raw: Any) -> List[Dict[str, float]]:
    """
    Accept:
      - [{lat,lon}, ...]
      - [[lon,lat], ...]  (also tolerates [lat,lon] and swaps via heuristic)
    Return: list of {lon, lat} dicts.
    """
    out: List[Dict[str, float]] = []
    if raw is None:
        return out
    for item in raw:
        if isinstance(item, dict) and "lat" in item and "lon" in item:
            out.append({"lat": float(item["lat"]), "lon": float(item["lon"])})
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            a = float(item[0])
            b = float(item[1])
            # Heuristic swap if the first looks like lat and the second like lon
            # (lat in [-90,90], lon in [-180,180])
            if abs(a) <= 90 and abs(b) > 90:
                a, b = b, a
            out.append({"lon": a, "lat": b})
        else:
            raise ValueError(f"Bad coordinate item: {item!r}")
    return out


class MatrixRequest(BaseModel):
    # Adapter & mode are free-form strings (no Literal)
    adapter: str
    mode: str = "driving"
    parameters: Optional[Dict[str, Any]] = None

    # You may send either origins+destinations, or a single coordinates array
    origins: Optional[List[Coordinate]] = None
    destinations: Optional[List[Coordinate]] = None
    coordinates: Optional[List[Coordinate]] = None

    @root_validator(pre=True)
    def fill_and_coerce(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        # Coerce any incoming coord shapes BEFORE field validation
        for key in ("origins", "destinations", "coordinates"):
            if key in values and values[key] is not None:
                values[key] = _coerce_coords(values[key])

        # If only `coordinates` was provided, use it for both O & D
        if (
            values.get("origins") is None or values.get("destinations") is None
        ) and values.get("coordinates"):
            values["origins"] = values.get("origins") or values["coordinates"]
            values["destinations"] = values.get("destinations") or values["coordinates"]

        # If still missing, raise (matches your old “Field required” but with clearer text)
        if values.get("origins") is None or values.get("destinations") is None:
            raise ValueError(
                "origins and destinations are required (or provide coordinates)"
            )
        return values

    @validator("origins", "destinations", pre=False)
    def non_empty(cls, v: List[Coordinate]) -> List[Coordinate]:
        if not v or len(v) < 1:
            raise ValueError("must contain at least 1 coordinate")
        return v


class MatrixResult(BaseModel):
    # Used by /solver/solve endpoint (solvers)
    # Distances in **kilometers**, durations in **seconds**
    distances: List[List[float]]
    durations: Optional[List[List[float]]] = None
    emissions: Optional[List[List[float]]] = None
    costs: Optional[List[List[float]]] = None
    # Optional coordinates aligned with matrix indices: [[lon, lat], ...]
    coordinates: Optional[List[List[float]]] = None

    @classmethod
    def from_ors(cls, data: Dict) -> "MatrixResult":
        # ORS returns distances in meters by default; convert to km
        raw_d = data.get("distances")
        raw_t = data.get("durations")
        distances_km = (
            [[(v or 0) / 1000.0 for v in row] for row in raw_d]
            if raw_d is not None
            else []
        )
        return cls(
            distances=distances_km,
            durations=raw_t if raw_t is not None else None,
        )

    @classmethod
    def from_google(cls, data: Dict) -> "MatrixResult":
        # Google Distance Matrix returns meters/seconds; convert meters -> km
        distances_km: List[List[float]] = []
        durations_s: List[List[float]] = []
        for row in data.get("rows", []):
            drow: List[float] = []
            trow: List[float] = []
            for element in row.get("elements", []):
                if element.get("status") == "OK":
                    drow.append(float(element["distance"]["value"]) / 1000.0)  # km
                    trow.append(float(element["duration"]["value"]))  # s
                else:
                    drow.append(float("inf"))
                    trow.append(float("inf"))
            distances_km.append(drow)
            durations_s.append(trow)
        return cls(distances=distances_km, durations=durations_s)
