# services/solvers/vroom_solver.py
from __future__ import annotations
from typing import List, Optional, Tuple, Any
import inspect
import math
import os

from core.interfaces import VRPSolver
from core.exceptions import SolverRequestError
from models.solvers import SolveRequest, Routes, Route
from models.fleet import Vehicle
from models.distance_matrix import MatrixResult

try:
    from vroom import Vehicle as VroomVehicle, Job as VroomJob, Input as VroomInput

    _HAS_VROOM = True
except Exception:
    VroomVehicle = VroomJob = VroomInput = None  # type: ignore
    _HAS_VROOM = False


def _vehicles(fleet_obj) -> List[Vehicle]:
    return (
        list(fleet_obj.vehicles) if hasattr(fleet_obj, "vehicles") else list(fleet_obj)
    )


# ---------- distance helpers (meters / seconds) ----------


def _haversine_m(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """a,b in (lat, lon) → meters"""
    lat1, lon1 = float(a[0]), float(a[1])
    lat2, lon2 = float(b[0]), float(b[1])
    R = 6371000.0
    to_rad = math.pi / 180.0
    dlat = (lat2 - lat1) * to_rad
    dlon = (lon2 - lon1) * to_rad
    s1 = math.sin(dlat / 2.0)
    s2 = math.sin(dlon / 2.0)
    x = s1 * s1 + math.cos(lat1 * to_rad) * math.cos(lat2 * to_rad) * s2 * s2
    return 2.0 * R * math.asin(math.sqrt(max(0.0, x)))


def _geo_matrix(
    coords_latlon: List[Tuple[float, float]], avg_speed_kmh: float = 50.0
) -> Tuple[List[List[float]], List[List[float]]]:
    """
    Build distance (meters) and duration (seconds) matrices using Haversine + constant speed.
    """
    n = len(coords_latlon)
    dist = [[0.0] * n for _ in range(n)]
    dur = [[0.0] * n for _ in range(n)]
    mps = max(0.1, (avg_speed_kmh * 1000.0) / 3600.0)
    for i in range(n):
        for j in range(i + 1, n):
            d = _haversine_m(coords_latlon[i], coords_latlon[j])
            t = d / mps
            dist[i][j] = dist[j][i] = d
            dur[i][j] = dur[j][i] = t
    return dist, dur


def _nn_path(dist: List[List[float]], depot: int) -> List[int]:
    n = len(dist)
    unvisited = set(range(n))
    unvisited.discard(depot)
    route = [depot]
    cur = depot
    while unvisited:
        nxt = min(unvisited, key=lambda j: dist[cur][j])
        route.append(nxt)
        unvisited.remove(nxt)
        cur = nxt
    route.append(depot)
    return route


def _route_totals(
    path: List[int], matrix: MatrixResult, ef_kg_per_km: float | None = None
):
    """
    Distances are assumed to be METERS, durations SECONDS.
    Returns (total_distance_m, total_duration_s|None, emissions_kg|None)
    """
    total_dist_m = 0.0
    total_dur_s: Optional[float] = 0.0 if matrix.durations is not None else None
    for a, b in zip(path, path[1:]):
        total_dist_m += float(matrix.distances[a][b])
        if total_dur_s is not None:
            total_dur_s += float(matrix.durations[a][b])
    emissions = (
        (ef_kg_per_km or 0.0) * (total_dist_m / 1000.0) if ef_kg_per_km else None
    )
    return (
        total_dist_m,
        int(total_dur_s) if isinstance(total_dur_s, (int, float)) else None,
        emissions,
    )


# ---------- waypoint helpers ----------


def _coords_from_waypoints(waypoints: List[Any]) -> List[Tuple[float, float]]:
    """
    Returns list of (lat, lon) in the *same node order* as waypoints.
    Supports both:
      - {"lat": ..., "lon": ...}
      - {"location": {"lat": ..., "lon": ...}}
    """
    coords: List[Tuple[float, float]] = []
    for wp in waypoints:
        if isinstance(wp, dict):
            lat = wp.get("lat")
            lon = wp.get("lon")
            if lat is None or lon is None:
                loc = wp.get("location") or {}
                lat = loc.get("lat")
                lon = loc.get("lon")
        else:
            # Pydantic model instance
            lat = getattr(wp, "lat", None)
            lon = getattr(wp, "lon", None)
            if lat is None or lon is None:
                loc = getattr(wp, "location", None)
                lat = getattr(loc, "lat", None) if loc is not None else None
                lon = getattr(loc, "lon", None) if loc is not None else None

        if lat is None or lon is None:
            raise SolverRequestError(
                "Waypoint is missing lat/lon (either top-level or under .location)."
            )
        coords.append((float(lat), float(lon)))
    return coords


def _get_wp_meta(waypoints: Optional[List[Any]], idx: int):
    """
    Extract meta for job i (service seconds, demand vector, time window).
    Accepts frontend shape:
      { service: 600, demand: [1], time_window: {start,end} }
    Anything missing returns None.
    """
    svc = None
    dem = None
    tw = None
    if waypoints and 0 <= idx < len(waypoints):
        w = waypoints[idx]
        if isinstance(w, dict):
            svc = w.get("service")
            dem = w.get("demand")
            twd = w.get("time_window") or {}
            if "start" in twd and "end" in twd:
                tw = (int(twd["start"]), int(twd["end"]))
        else:
            svc = getattr(w, "service", None)
            dem = getattr(w, "demand", None)
            twd = getattr(w, "time_window", None)
            if twd is not None and hasattr(twd, "start") and hasattr(twd, "end"):
                tw = (int(twd.start), int(twd.end))
    # normalize
    svc = int(svc) if isinstance(svc, (int, float)) else None
    if isinstance(dem, (int, float)):
        dem = [int(dem)]
    elif isinstance(dem, (list, tuple)):
        dem = [int(x) for x in dem]
    else:
        dem = None
    return svc, dem, tw


def _coerce_delivery_to_capacity(
    delivery: Optional[List[int]], capacity: Optional[List[int]]
) -> Optional[List[int]]:
    """
    Ensure the delivery vector length matches vehicle capacity dims when provided.
    """
    if delivery is None:
        return None
    if not capacity or not isinstance(capacity, (list, tuple)) or len(capacity) == 0:
        return delivery  # vehicle has no capacity dims → it's fine
    m = len(capacity)
    if len(delivery) < m:
        delivery = delivery + [0] * (m - len(delivery))
    elif len(delivery) > m:
        delivery = delivery[:m]
    return delivery


class VroomSolver(VRPSolver):
    def solve(self, request: SolveRequest) -> Routes:
        # ---- normalize fleet / depot ----
        vehicles = _vehicles(request.fleet)
        if not vehicles:
            raise SolverRequestError("VroomSolver: fleet is empty.")
        depot = int(request.depot_index or 0)

        # ---- normalize matrix (optional) ----
        matrix: Optional[MatrixResult] = None
        if request.matrix is not None:
            if isinstance(request.matrix, MatrixResult):
                matrix = request.matrix
            elif isinstance(request.matrix, dict):
                matrix = MatrixResult(**request.matrix)
            else:
                raise SolverRequestError(
                    f"Unsupported matrix type: {type(request.matrix)}"
                )

        # We'll want waypoint metadata for jobs (service, demand, TW) if present
        waypoints_list = list(getattr(request, "waypoints", []) or [])

        # ---- If no matrix, derive from waypoints (coordinate-mode) ----
        coords_latlon: Optional[List[Tuple[float, float]]] = None
        if matrix is None:
            if not waypoints_list:
                raise SolverRequestError(
                    "VROOM needs either 'matrix' or 'waypoints' (coordinate mode)."
                )
            coords_latlon = _coords_from_waypoints(waypoints_list)
            dist, durations = _geo_matrix(coords_latlon, avg_speed_kmh=50.0)
            matrix = MatrixResult(distances=dist, durations=durations)
        else:
            coords_latlon = None  # matrix mode; we may still use waypoint meta below

        # basic sanity
        n = len(matrix.distances)
        if not (0 <= depot < n):
            raise SolverRequestError(
                f"Invalid depot_index {depot} for matrix size {n}."
            )

        # ---- No pyvroom? fallback NN on our matrix (single consolidated route) ----
        if not _HAS_VROOM:
            path = _nn_path(matrix.distances, depot)
            td, tt, em = _route_totals(
                path, matrix, getattr(vehicles[0], "emissions_per_km", None)
            )
            return Routes(
                status="success",
                message="Fallback NN solution (pyvroom not available)",
                routes=[
                    Route(
                        vehicle_id=str(vehicles[0].id),
                        waypoint_ids=[str(i) for i in path],
                        total_distance=td,
                        total_duration=tt,
                        emissions=em,
                    )
                ],
            )

        # ---- pyvroom input ----
        try:
            inp = VroomInput()

            # Vehicle constructor probing
            v_sig = inspect.signature(VroomVehicle.__init__)
            v_params = set(v_sig.parameters.keys())

            # Job signature probing (to decide index vs coord mode)
            j_sig = inspect.signature(VroomJob.__init__)
            j_params = set(j_sig.parameters.keys())

            coord_mode = False
            index_kw = None
            if "location_index" in j_params:
                index_kw = "location_index"  # modern builds
            elif "index" in j_params:
                index_kw = "index"  # some builds
            elif "location" in j_params:
                coord_mode = True  # coordinates-only build
            else:
                raise SolverRequestError(
                    "Unrecognized pyvroom Job signature; cannot set location/index."
                )

            # If coord-mode and we don't have coords yet, try to discover some or fallback
            if coord_mode and coords_latlon is None:
                coords = getattr(matrix, "coordinates", None)
                if (
                    coords
                    and len(coords) == n
                    and isinstance(coords[0], (list, tuple))
                    and len(coords[0]) == 2
                ):
                    # matrix may store [lon,lat]; convert to (lat,lon)
                    coords_latlon = [(float(c[1]), float(c[0])) for c in coords]
                else:
                    path = _nn_path(matrix.distances, depot)
                    td, tt, em = _route_totals(
                        path, matrix, getattr(vehicles[0], "emissions_per_km", None)
                    )
                    return Routes(
                        status="success",
                        message="pyvroom requires coordinates but none provided; fallback NN used",
                        routes=[
                            Route(
                                vehicle_id=str(vehicles[0].id),
                                waypoint_ids=[str(i) for i in path],
                                total_distance=td,
                                total_duration=tt,
                                emissions=em,
                            )
                        ],
                    )

            # ---- Vehicles ----
            for k, v0 in enumerate(vehicles):
                start_idx = int(getattr(v0, "start", depot) or depot)
                end_idx = int(getattr(v0, "end", depot) or depot)
                capacity = getattr(v0, "capacity", []) or []

                v_kwargs = {}
                if coord_mode:
                    # Vehicles expect coordinates [lon,lat]
                    if coords_latlon is None:
                        path = _nn_path(matrix.distances, depot)
                        td, tt, em = _route_totals(
                            path, matrix, getattr(vehicles[0], "emissions_per_km", None)
                        )
                        return Routes(
                            status="success",
                            message="pyvroom coordinate mode lacked coords; fallback NN used",
                            routes=[
                                Route(
                                    vehicle_id=str(vehicles[0].id),
                                    waypoint_ids=[str(i) for i in path],
                                    total_distance=td,
                                    total_duration=tt,
                                    emissions=em,
                                )
                            ],
                        )
                    start_ll = coords_latlon[start_idx]
                    end_ll = coords_latlon[end_idx]
                    start_xy = [float(start_ll[1]), float(start_ll[0])]
                    end_xy = [float(end_ll[1]), float(end_ll[0])]

                    if "start" in v_params:
                        v_kwargs["start"] = start_xy
                    elif "start_index" in v_params:
                        v_kwargs["start_index"] = start_idx
                    else:
                        raise SolverRequestError(
                            "pyvroom Vehicle.__init__ lacks 'start'/'start_index'."
                        )

                    if "end" in v_params:
                        v_kwargs["end"] = end_xy
                    elif "end_index" in v_params:
                        v_kwargs["end_index"] = end_idx
                else:
                    # Index mode
                    if "start_index" in v_params:
                        v_kwargs["start_index"] = start_idx
                    elif "start" in v_params:
                        v_kwargs["start"] = start_idx
                    else:
                        raise SolverRequestError(
                            "pyvroom Vehicle.__init__ lacks 'start'/'start_index'."
                        )

                    if "end_index" in v_params:
                        v_kwargs["end_index"] = end_idx
                    elif "end" in v_params:
                        v_kwargs["end"] = end_idx

                if "capacity" in v_params:
                    v_kwargs["capacity"] = capacity

                veh_obj = VroomVehicle(k, **v_kwargs)
                inp.add_vehicle(veh_obj)

            # ---- Jobs (all nodes except depot) ----
            for loc in range(n):
                if loc == depot:
                    continue
                # extract meta (if waypoints list exists, we assume same order as matrix indices)
                svc, dem, tw = _get_wp_meta(waypoints_list, loc)
                # coerce delivery vector to capacity dims of the FIRST vehicle (typical single-veh TSP)
                cap_dims = getattr(vehicles[0], "capacity", []) or []
                delivery_vec = _coerce_delivery_to_capacity(dem, cap_dims)

                j_kwargs = {}
                if svc is not None:
                    j_kwargs["service"] = svc
                if delivery_vec is not None:
                    j_kwargs["delivery"] = delivery_vec
                if tw is not None:
                    j_kwargs["time_windows"] = [tw]

                if coord_mode:
                    # vroom wants [lon, lat]
                    ll = coords_latlon[loc] if coords_latlon is not None else None
                    if ll is None:
                        raise SolverRequestError(
                            "Internal: missing coordinates for job in coord mode."
                        )
                    job_xy = [float(ll[1]), float(ll[0])]
                    job = VroomJob(loc, location=job_xy, **j_kwargs)
                else:
                    if "location_index" in (
                        inspect.signature(VroomJob.__init__).parameters.keys()
                    ):
                        job = VroomJob(loc, location_index=loc, **j_kwargs)
                    elif "index" in (
                        inspect.signature(VroomJob.__init__).parameters.keys()
                    ):
                        job = VroomJob(loc, index=loc, **j_kwargs)
                    else:
                        # should not happen because of earlier probing
                        job = VroomJob(loc, **j_kwargs)

                inp.add_job(job)

            # ---- Inject costs (bypass OSRM) ----
            durations = (
                matrix.durations
                if matrix.durations is not None
                else [[0.0] * n for _ in range(n)]
            )
            if hasattr(inp, "set_costs"):
                inp.set_costs(matrix.distances, durations)  # meters + seconds
            else:
                if hasattr(inp, "set_durations"):
                    inp.set_durations(durations)
                if hasattr(inp, "set_distances"):
                    inp.set_distances(matrix.distances)

            # ---- Solve with version-compatible signature handling ----
            threads = max(1, (os.cpu_count() or 1))
            try:
                solve_sig = inspect.signature(inp.solve)
            except (TypeError, ValueError):
                solve_sig = None

            # Build kwargs if the method exposes those names
            kw = {}
            if solve_sig:
                params = solve_sig.parameters
            if "nb_threads" in params:
                kw["nb_threads"] = threads
            elif "num_threads" in params:
                kw["num_threads"] = threads
            if "exploration_level" in params:
                kw["exploration_level"] = 5

            # Try kwargs first, then positional fallbacks
            try:
                if kw:
                    sol = inp.solve(**kw)
                else:
                    # some older builds need pure positional: (nb_threads, exploration_level)
                    try:
                        sol = inp.solve(threads, 5)
                    except TypeError:
                        # minimal required positional (nb_threads)
                        sol = inp.solve(threads)
            except TypeError:
                # last resort: try exploration-only, then bare
                try:
                    sol = inp.solve(exploration_level=5)
                except TypeError:
                    sol = inp.solve()

            # No routes? fallback NN as one consolidated route on vehicle 0
            if not hasattr(sol, "routes") or not sol.routes:
                path = _nn_path(matrix.distances, depot)
                td, tt, em = _route_totals(
                    path, matrix, getattr(vehicles[0], "emissions_per_km", None)
                )
                return Routes(
                    status="success",
                    message="VROOM returned empty; fallback NN used",
                    routes=[
                        Route(
                            vehicle_id=str(vehicles[0].id),
                            waypoint_ids=[str(i) for i in path],
                            total_distance=td,
                            total_duration=tt,
                            emissions=em,
                        )
                    ],
                )

            # ---- Extract per-vehicle routes ----
            out_routes: List[Route] = []
            for r in sol.routes:
                k = getattr(r, "vehicle", None)
                veh_id = (
                    str(vehicles[k].id)
                    if isinstance(k, int) and 0 <= k < len(vehicles)
                    else str(vehicles[0].id)
                )

                path: List[int] = []
                start_idx = int(
                    getattr(vehicles[k], "start", depot)
                    if isinstance(k, int)
                    else depot
                )
                end_idx = int(
                    getattr(vehicles[k], "end", depot) if isinstance(k, int) else depot
                )
                path.append(start_idx)

                for st in getattr(r, "steps", []):
                    li = getattr(st, "location_index", None)
                    if li is None:
                        li = getattr(st, "job", None)
                    if isinstance(li, int) and li != start_idx:
                        path.append(li)

                if path[-1] != end_idx:
                    path.append(end_idx)

                td, tt, em = _route_totals(
                    path,
                    matrix,
                    getattr(
                        vehicles[k if isinstance(k, int) else 0],
                        "emissions_per_km",
                        None,
                    ),
                )
                out_routes.append(
                    Route(
                        vehicle_id=veh_id,
                        waypoint_ids=[str(i) for i in path],
                        total_distance=td,  # meters
                        total_duration=tt,  # seconds
                        emissions=em,
                    )
                )

            return Routes(status="success", message="VROOM solution", routes=out_routes)

        except SolverRequestError:
            raise
        except TypeError as te:
            raise SolverRequestError(f"pyvroom ctor failed: {te}")
        except Exception as e:
            # Last resort: one NN route on vehicle 0
            path = _nn_path(matrix.distances, depot)
            td, tt, em = _route_totals(
                path, matrix, getattr(vehicles[0], "emissions_per_km", None)
            )
            return Routes(
                status="success",
                message=f"pyvroom error: {e}; fallback NN used",
                routes=[
                    Route(
                        vehicle_id=str(vehicles[0].id),
                        waypoint_ids=[str(i) for i in path],
                        total_distance=td,
                        total_duration=tt,
                        emissions=em,
                    )
                ],
            )
