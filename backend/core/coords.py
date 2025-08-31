# backend/core/coords.py
from __future__ import annotations
from math import cos, pi
from typing import Iterable, Tuple, Dict, Any, Optional

EUCLIDEAN_TYPES = {"EUC_2D", "EUC_3D", "ATT"}


def _deg_per_km(lat_deg: float) -> Tuple[float, float]:
    # ~km per degree latitude/longitude
    km_per_deg_lat = 111.32
    km_per_deg_lon = max(1e-6, 111.32 * cos(lat_deg * pi / 180.0))
    return (1.0 / km_per_deg_lon, 1.0 / km_per_deg_lat)


def looks_euclidean(
    edge_weight_type: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    waypoints: Optional[Iterable[Dict[str, Any]]] = None,
) -> bool:
    """Heuristic: header says EUC_* OR we see x/y on waypoints OR Solomon format."""
    if edge_weight_type and edge_weight_type.strip().upper() in EUCLIDEAN_TYPES:
        return True
    mf = (meta or {}).get("format", "")
    if isinstance(mf, str) and ("solomon" in mf.lower() or "vrplib" in mf.lower()):
        # May still be GEO, but in your loaders we keep x,y for planar; safe to synthesize display
        pass
    if waypoints:
        for w in waypoints:
            if "x" in w and "y" in w:
                return True
    return False


def add_display_lonlat_from_euclidean(
    waypoints: Iterable[Dict[str, Any]],
    anchor_lon: float = 0.0,
    anchor_lat: float = 0.0,
    scale_km: float = 40.0,
    flip_y: bool = True,
    x_field: str = "x",
    y_field: str = "y",
    out_lon: str = "lon",
    out_lat: str = "lat",
) -> None:
    """
    Mutates each waypoint dict in-place:
      expects planar coordinates in waypoints[*][x_field], [y_field],
      and writes map-display coordinates to [out_lon], [out_lat] (WGS84-ish).
    """
    pts = []
    for w in waypoints:
        if w.get(x_field) is None or w.get(y_field) is None:
            continue
        pts.append((float(w[x_field]), float(w[y_field])))
    if not pts:
        return

    xs, ys = zip(*pts)
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    span = max(maxx - minx, maxy - miny) or 1.0

    dlon_per_km, dlat_per_km = _deg_per_km(anchor_lat)
    width_deg = scale_km * dlon_per_km
    height_deg = scale_km * dlat_per_km

    for w in waypoints:
        if w.get(x_field) is None or w.get(y_field) is None:
            continue
        nx = (float(w[x_field]) - cx) / span
        ny = (float(w[y_field]) - cy) / span
        if flip_y:
            ny = -ny
        w[out_lon] = anchor_lon + nx * width_deg
        w[out_lat] = anchor_lat + ny * height_deg
