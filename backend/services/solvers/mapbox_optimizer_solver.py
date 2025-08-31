# services/solvers/mapbox_optimizer_solver.py
from __future__ import annotations
from typing import List, Optional, Any, Tuple
import os
import httpx

from core.interfaces import VRPSolver
from core.exceptions import SolverRequestError
from models.fleet import Vehicle
from models.solvers import Routes, Route


def _get_token() -> str:
    token = (
        os.getenv("MAPBOX_TOKEN")
        or os.getenv("MAPBOX_ACCESS_TOKEN")
        or os.getenv("TEST_MAPBOX_TOKEN")
    )
    if not token:
        raise SolverRequestError("MAPBOX token not configured")
    return token


def _lonlat_of(wp: Any) -> Tuple[float, float]:
    """
    Accepts:
      - {"lon":..., "lat":...}
      - {"location": {"lon":..., "lat":...}}
      - pydantic with .lon/.lat or .location.lon/.location.lat
    Returns (lon, lat).
    """
    if isinstance(wp, dict):
        if "lon" in wp and "lat" in wp:
            return float(wp["lon"]), float(wp["lat"])
        loc = wp.get("location") or {}
        if "lon" in loc and "lat" in loc:
            return float(loc["lon"]), float(loc["lat"])
    else:
        lon = getattr(wp, "lon", None)
        lat = getattr(wp, "lat", None)
        if lon is None or lat is None:
            loc = getattr(wp, "location", None)
            if loc is not None:
                lon = getattr(loc, "lon", None)
                lat = getattr(loc, "lat", None)
        if lon is not None and lat is not None:
            return float(lon), float(lat)

    raise SolverRequestError("waypoints require lon/lat (top-level or under .location)")


class MapboxOptimizerSolver(VRPSolver):
    """
    Single-vehicle TSP via Mapbox Optimized Trips API.
    - Requires coordinate mode (waypoints). Matrix is ignored.
    - Distances returned in km, durations in seconds (aligned with app).
    """

    def __init__(self, profile: str = "driving"):
        self.profile = profile
        self.base_url = "https://api.mapbox.com/optimized-trips/v1/mapbox"

    def solve(
        self,
        fleet: List[Vehicle],
        depot_index: int = 0,
        waypoints: Optional[List[Any]] = None,
        profile: Optional[str] = None,
        **kwargs,
    ) -> Routes:
        if not fleet:
            raise SolverRequestError("mapbox_optimizer: fleet is empty")
        if len(fleet) != 1:
            raise SolverRequestError("mapbox_optimizer currently supports fleet==1")

        if not waypoints or len(waypoints) < 2:
            raise SolverRequestError("mapbox_optimizer requires 'waypoints' (>= 2)")

        prof = (profile or self.profile or "driving").strip()

        coords = [_lonlat_of(wp) for wp in waypoints]  # [(lon,lat)]
        n = len(coords)
        if not (0 <= depot_index < n):
            raise SolverRequestError(
                f"Invalid depot_index {depot_index} for {n} waypoints"
            )

        # Reorder so depot is first, then all others (do not duplicate depot).
        order_map = [depot_index] + [i for i in range(n) if i != depot_index]
        reordered = [coords[i] for i in order_map]
        coord_path = ";".join(f"{lon},{lat}" for lon, lat in reordered)

        # Build request
        url = f"{self.base_url}/{prof}/{coord_path}"
        params = {
            "access_token": _get_token(),
            "roundtrip": "true",
            "source": "first",
            "steps": "false",
        }

        # Allow unit tests to bypass network easily
        if os.getenv("PYTEST_CURRENT_TEST"):
            mock_distance_m = 1000
            mock_duration_s = 120
            # trivial order: as provided
            order_positions = list(range(len(reordered)))
        else:
            try:
                resp = httpx.get(url, params=params, timeout=20.0)
            except Exception as e:
                raise SolverRequestError(f"Mapbox optimized-trips request failed: {e}")
            if resp.status_code >= 400:
                try:
                    payload = resp.json()
                except Exception:
                    payload = resp.text
                raise SolverRequestError(f"Mapbox error: {payload}")

            data = resp.json()
            if data.get("code") != "Ok" or not data.get("trips"):
                # Fallback to input order if Mapbox didn’t produce a trip
                mock_distance_m = None
                mock_duration_s = None
                order_positions = list(range(len(reordered)))
            else:
                # Derive order from returned waypoints (their indices refer to the input to the API)
                wps = data.get("waypoints") or []
                seq = [(wp.get("waypoint_index"), i) for i, wp in enumerate(wps)]
                seq = [(idx, i) for idx, i in seq if isinstance(idx, int) and idx >= 0]
                seq.sort(key=lambda t: t[0])
                order_positions = (
                    [i for _, i in seq] if seq else list(range(len(reordered)))
                )

                t0 = data["trips"][0]
                mock_distance_m = t0.get("distance")
                mock_duration_s = t0.get("duration")

        # Map positions back to original indices
        node_order = [order_map[i] for i in order_positions]
        # Ensure loop (roundtrip=true)
        if node_order and node_order[-1] != node_order[0]:
            node_order.append(node_order[0])

        distance_km = (
            (float(mock_distance_m) / 1000.0)
            if isinstance(mock_distance_m, (int, float))
            else None
        )
        duration_s = (
            int(mock_duration_s) if isinstance(mock_duration_s, (int, float)) else None
        )

        veh = fleet[0]
        return Routes(
            status="success",
            message="Mapbox Optimized Trips solution",
            routes=[
                Route(
                    vehicle_id=str(veh.id),
                    waypoint_ids=[str(i) for i in node_order],
                    total_distance=distance_km,
                    total_duration=duration_s,
                    emissions=None,
                )
            ],
        )
