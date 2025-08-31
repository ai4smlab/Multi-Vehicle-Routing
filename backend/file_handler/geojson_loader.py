# services/file_loader/geojson_loader.py
import json
from models.waypoints import Waypoint


def load_geojson_points(path: str) -> list[Waypoint]:
    data = json.loads(open(path, "r", encoding="utf-8").read())
    wps: list[Waypoint] = []
    for i, feat in enumerate(data.get("features", []), start=1):
        if feat.get("geometry", {}).get("type") != "Point":
            continue
        lon, lat = feat["geometry"]["coordinates"]
        props = feat.get("properties", {}) or {}
        wps.append(
            Waypoint(
                id=str(props.get("id", props.get("name", i))),
                lat=float(lat),
                lon=float(lon),
                demand=int(props.get("demand", 0)) or 0,
                service_time=int(props.get("service_time", 0)) or 0,
                time_window=props.get("time_window"),  # [start,end] if present
                depot=bool(props.get("depot", False)),
            )
        )
    return wps
