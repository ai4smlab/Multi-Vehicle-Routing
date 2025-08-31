# api/coord_utils.py
from typing import List, Dict, Tuple, Union
from fastapi import HTTPException

CoordInput = Union[List[float], Tuple[float, float], Dict[str, float]]


def normalize_coords(coords: List[CoordInput]) -> Tuple[str, List[Dict[str, float]]]:
    """
    Accept [[lon,lat], ...] or [{lon,lat}, ...] and return:
      ( "lon,lat;...", [ {lon:float, lat:float}, ... ] )
    """
    if not isinstance(coords, list) or len(coords) < 2:
        raise HTTPException(400, "Need at least 2 coordinates")
    norm: List[Dict[str, float]] = []
    for c in coords:
        if isinstance(c, dict):
            try:
                lon = float(c["lon"])
                lat = float(c["lat"])
            except Exception:
                raise HTTPException(
                    400,
                    "coordinates items must be objects with numeric 'lon' and 'lat'",
                )
            norm.append({"lon": lon, "lat": lat})
        elif isinstance(c, (list, tuple)) and len(c) >= 2:
            lon = float(c[0])
            lat = float(c[1])
            norm.append({"lon": lon, "lat": lat})
        else:
            raise HTTPException(
                400, "coordinates must be [[lon,lat],...] or [{lon,lat},...]"
            )
    path = ";".join(f"{c['lon']},{c['lat']}" for c in norm)
    return path, norm
