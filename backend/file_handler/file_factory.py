# file_handler/file_factory.py
from __future__ import annotations
from pathlib import Path
from typing import Callable, Dict, Any
import math

from .vrplib_lib_wrapper import load_with_vrplib, VRPLIB_AVAILABLE
from .xml_loader import VRPSetXMLLoader
from .solomon_loader import load_solomon_txt
from .vrplib_loader import load_vrplib as load_cvrplib_like

# OPTIONAL: CSV/GeoJSON lightweight loaders (if present)
try:
    from file_handler.csv_loader import load_csv_points  # returns Waypoint[]
except Exception:
    load_csv_points = None  # type: ignore

try:
    from file_handler.geojson_loader import load_geojson_points  # returns Waypoint[]
except Exception:
    load_geojson_points = None  # type: ignore

_xml = VRPSetXMLLoader()


def _vrp_loader(path: str, **kw: Any):
    if VRPLIB_AVAILABLE:
        try:
            return load_with_vrplib(path, **kw)
        except Exception:
            pass
    text = Path(path).read_text(encoding="utf-8", errors="ignore").lstrip()
    if text.startswith("<"):
        return _xml.load_file(path, compute_matrix=kw.get("compute_matrix", True))
    if "VEHICLE" in text and "CUSTOMER" in text:
        return load_solomon_txt(path, **kw)
    return load_cvrplib_like(path, **kw)


def _xml_loader(path: str, **kw: Any):
    return _xml.load_file(path, compute_matrix=kw.get("compute_matrix", True))


def _txt_loader(path: str, **kw):
    with open(path, "r", errors="ignore") as f:
        head = f.read(500)
    head_upper = head.upper()
    if "VEHICLE" in head_upper and ("CUSTOMER" in head_upper or "CUST" in head_upper):
        return load_solomon_txt(path, **kw)
    return load_cvrplib_like(path, **kw)


_LOADER_REGISTRY: Dict[str, Callable] = {
    ".vrp": _vrp_loader,
    ".xml": _xml_loader,
    ".txt": _txt_loader,
}


def list_supported_extensions():
    return sorted(_LOADER_REGISTRY.keys())


def get_loader_for_filename(filename: str):
    ext = Path(filename).suffix.lower()
    if ext in _LOADER_REGISTRY:
        return _LOADER_REGISTRY[ext]
    raise ValueError(f"No loader for '{ext}'. Supported: {list_supported_extensions()}")


# ---------- a general-purpose 'load_any' helper ----------


def _to_std_waypoint_dicts(waypoints_model_list) -> list[dict]:
    """
    Normalize CSV/GeoJSON Waypoint models to the same dict schema your XML/Solomon loaders emit:
      { id, lat, lon, demand, service_time, time_window, depot }
    """
    out = []
    for wp in waypoints_model_list:
        # pydantic object or dict
        data = wp.model_dump() if hasattr(wp, "model_dump") else dict(wp)
        # CSV/GeoJSON loaders use fields: id, lat, lon, demand, service_time, time_window, depot
        out.append(
            {
                "id": str(data.get("id")),
                "lat": float(data.get("lat")),
                "lon": float(data.get("lon")),
                "demand": int(data.get("demand") or 0),
                "service_time": int(data.get("service_time") or 0),
                "time_window": data.get("time_window"),
                "depot": bool(data.get("depot") or False),
            }
        )
    return out


def _euclid_matrix_from_latlon(pts: list[tuple[float, float]]) -> dict:
    """
    Simple planar (lat,lon) Euclidean matrix builder, just like xml_loader's fallback.
    Returns { "distances": [[...]], "durations": [[...]] } (durations == distances).
    """
    n = len(pts)
    dist = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1])
            dist[i][j] = dist[j][i] = d
    return {"distances": dist, "durations": [row[:] for row in dist]}


def load_any(
    path: str, kind: str | None = None, compute_matrix: bool = True, **kw
) -> dict:
    """
    Unified loader:
      - kind == 'csv' or file ends with .csv  -> use load_csv_points (if available)
      - kind == 'geojson' or file ends with .geojson/.json -> use load_geojson_points (if available)
      - else -> delegate to existing registry (.vrp/.xml/.txt)
    Returns a dict consistent with other loaders:
      { waypoints, fleet?, depot_index?, matrix?, meta? }
    """
    p = Path(path)
    ext = p.suffix.lower()

    # CSV
    if kind == "csv" or ext == ".csv":
        if not load_csv_points:
            raise ValueError(
                "CSV support not available (services.file_loader.csv_loader not found)."
            )
        wps_models = load_csv_points(str(p))
        wps = _to_std_waypoint_dicts(wps_models)
        depot_index = next((i for i, w in enumerate(wps) if w.get("depot")), 0)
        matrix = (
            _euclid_matrix_from_latlon([(w["lat"], w["lon"]) for w in wps])
            if compute_matrix
            else None
        )
        return {
            "waypoints": wps,
            "fleet": {"vehicles": []},
            "depot_index": depot_index,
            "matrix": matrix,
            "meta": {"source": p.name, "format": "csv"},
        }

    # GeoJSON
    if kind in ("geojson", "json") or ext in (".geojson", ".json"):
        if not load_geojson_points:
            raise ValueError(
                "GeoJSON support not available (services.file_loader.geojson_loader not found)."
            )
        wps_models = load_geojson_points(str(p))
        wps = _to_std_waypoint_dicts(wps_models)
        depot_index = next((i for i, w in enumerate(wps) if w.get("depot")), 0)
        matrix = (
            _euclid_matrix_from_latlon([(w["lat"], w["lon"]) for w in wps])
            if compute_matrix
            else None
        )
        return {
            "waypoints": wps,
            "fleet": {"vehicles": []},
            "depot_index": depot_index,
            "matrix": matrix,
            "meta": {"source": p.name, "format": "geojson"},
        }

    # Fallback to existing handlers (.vrp, .xml, .txt)
    loader = get_loader_for_filename(p.name)
    return loader(str(p), compute_matrix=compute_matrix, **kw)
