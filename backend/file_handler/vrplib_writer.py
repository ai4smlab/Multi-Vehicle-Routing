# services/file_loader/vrplib_writer.py
from __future__ import annotations
from pathlib import Path
from typing import List, Optional

# Use your models if present; otherwise accept simple dicts with the same keys
try:
    from models.waypoints import Waypoint  # noqa: F401
except Exception:
    Waypoint = None  # type: ignore

try:
    from models.fleet import Fleet  # noqa: F401
except Exception:
    Fleet = None  # type: ignore


def _get_capacity_from_fleet(fleet) -> int:
    """
    Supports either models.fleet.Fleet or a dict with Fleet-like structure.
    """
    if fleet is None:
        return 10**9
    # Pydantic model case
    if hasattr(fleet, "vehicles") and fleet.vehicles:
        cap = getattr(fleet.vehicles[0], "capacity", None)
        if isinstance(cap, (list, tuple)) and cap:
            return int(cap[0])
    # Dict case
    if isinstance(fleet, dict):
        vehicles = fleet.get("vehicles") or []
        if vehicles:
            cap = vehicles[0].get("capacity")
            if isinstance(cap, (list, tuple)) and cap:
                return int(cap[0])
    return 10**9


def write_vrplib(
    path: str | Path, waypoints: List, fleet, name: str = "INSTANCE"
) -> None:
    """
    Emit a simple CVRPLIB-like .vrp (nodes, demands, depot, capacity).
    `waypoints`: either list[Waypoint] or list[dict] with keys:
        id (str), lat (float), lon (float), demand (int), depot (bool)
    `fleet`: Fleet model or dict with {"vehicles":[{"capacity":[int]}]}
    """
    p = Path(path)
    lines: List[str] = []
    cap = _get_capacity_from_fleet(fleet)

    # Header
    lines.append(f"NAME : {name}")
    lines.append("TYPE : CVRP")
    lines.append(f"DIMENSION : {len(waypoints)}")
    lines.append(f"CAPACITY : {cap}")

    # Coordinates (planar)
    lines.append("NODE_COORD_SECTION")
    for i, wp in enumerate(waypoints, start=1):
        lat = float(getattr(wp, "lat", wp.get("lat")))
        lon = float(getattr(wp, "lon", wp.get("lon")))
        lines.append(f"{i} {lat:.6f} {lon:.6f}")

    # Demands
    lines.append("DEMAND_SECTION")
    for i, wp in enumerate(waypoints, start=1):
        demand = int(getattr(wp, "demand", wp.get("demand", 0)) or 0)
        lines.append(f"{i} {demand}")

    # Depot (first with depot=True or fallback to 1)
    depot_line: Optional[int] = None
    for i, wp in enumerate(waypoints, start=1):
        depot_flag = getattr(wp, "depot", wp.get("depot", False))
        if depot_flag:
            depot_line = i
            break
    if depot_line is None:
        depot_line = 1

    lines.append("DEPOT_SECTION")
    lines.append(str(depot_line))
    lines.append("-1")
    lines.append("EOF")

    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
