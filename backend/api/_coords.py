# api/_coords.py  (new tiny util)
from typing import Iterable, List, Dict, Any


def coerce_coords(items: Iterable[Any]) -> List[Dict[str, float]]:
    """
    Accept:
      - [{"lon":-73.9,"lat":40.7}, ...]
      - [[-73.9, 40.7], ...]
      - {"coordinates":[...]} wrappers (best-effort)
    Return: [{"lon":..,"lat":..}, ...] or raise ValueError.
    """
    if items is None:
        raise ValueError("coordinates missing")

    # unwrap common wrapper
    if isinstance(items, dict) and "coordinates" in items:
        items = items["coordinates"]  # type: ignore

    out: List[Dict[str, float]] = []
    for it in items:  # type: ignore
        if isinstance(it, dict) and "lon" in it and "lat" in it:
            out.append({"lon": float(it["lon"]), "lat": float(it["lat"])})
        elif (
            isinstance(it, (list, tuple))
            and len(it) >= 2
            and all(isinstance(x, (int, float)) for x in it[:2])
        ):
            out.append({"lon": float(it[0]), "lat": float(it[1])})
        else:
            raise ValueError("each coordinate must be {lon,lat} or [lon,lat]")
    if len(out) < 2:
        raise ValueError("need at least 2 coordinates")
    return out
