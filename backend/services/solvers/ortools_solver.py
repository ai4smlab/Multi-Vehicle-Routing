# services/solvers/ortools_solver.py
from __future__ import annotations
from typing import List, Optional, Any, Tuple
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from core.interfaces import VRPSolver
from core.exceptions import SolverError
from models.distance_matrix import MatrixResult
from models.fleet import Vehicle
from models.solvers import Routes, Route, PickupDeliveryPair

INF = 10**9  # large horizon for Time dimension


# ----------------------------
# Normalization helpers
# ----------------------------
def _align_len(arr, N, default):
    if arr is None:
        return [default] * N
    arr = list(arr)
    if len(arr) >= N:
        return arr[:N]
    return arr + [default] * (N - len(arr))


def _tw_pair_to_seconds(a, b) -> Tuple[int, int]:
    """Heuristic: treat small numbers as hours/minutes; else already seconds."""
    a = float(a if a is not None else 0)
    b = float(b if b is not None else 0)
    mx = max(a, b)
    if mx <= 48:  # hours → seconds
        return int(a * 3600), int(b * 3600)
    if mx <= 1440:  # minutes → seconds
        return int(a * 60), int(b * 60)
    return int(a), int(b)


def _svc_to_seconds(s) -> int:
    s = float(s or 0)
    if s <= 0:
        return 0
    if s <= 48:  # hours
        return int(s * 3600)
    if s <= 1440:  # minutes
        return int(s * 60)
    return int(s)  # seconds


def _normalize_inputs_for_matrix(
    *,
    matrix: MatrixResult,
    depot_index: int,
    demands,
    node_service_times,
    node_time_windows,
    vehicle_time_windows,  # list[(start,end)] or None
    vehicles_count: int,
):
    # Matrix shape
    N = len(matrix.distances or [])
    if N == 0 or any(len(row) != N for row in matrix.distances):
        raise SolverError(f"OR-Tools: distance matrix must be square; got N={N}")
    if matrix.durations is not None:
        if len(matrix.durations) != N or any(len(row) != N for row in matrix.durations):
            raise SolverError("OR-Tools: duration matrix shape mismatch with distances")

    depot = max(0, min(int(depot_index or 0), N - 1))

    dem = _align_len(demands, N, 0)
    svc = _align_len(node_service_times, N, 0)
    svc = [_svc_to_seconds(x) for x in svc]

    tw = _align_len(node_time_windows, N, (0, INF))
    tw_norm: List[Tuple[int, int]] = []
    for t in tw:
        if isinstance(t, (list, tuple)) and len(t) >= 2:
            a, b = t[0], t[1]
        else:
            a, b = 0, INF
        a2, b2 = _tw_pair_to_seconds(a, b)
        if a2 > b2:
            a2, b2 = b2, a2
        tw_norm.append((a2, b2))

    vtw = _align_len(vehicle_time_windows, vehicles_count, (0, INF))
    vtw_norm: List[Tuple[int, int]] = []
    for t in vtw:
        if isinstance(t, (list, tuple)) and len(t) >= 2:
            a, b = t[0], t[1]
        else:
            a, b = 0, INF
        a2, b2 = _tw_pair_to_seconds(a, b)
        if a2 > b2:
            a2, b2 = b2, a2
        vtw_norm.append((a2, b2))

    return {
        "N": N,
        "depot": depot,
        "demands": dem,
        "service_times": svc,
        "node_time_windows": tw_norm,
        "vehicle_time_windows": vtw_norm,
    }


class OrToolsSolver(VRPSolver):
    """
    CVRP / VRPTW / PDPTW using OR-Tools.
    - Arc cost: weighted distance + optional time
    - Capacities
    - Time windows (node & optional vehicle TWs)
    - Service times (added at the 'from' node)
    - Pickup & delivery (same-vehicle + precedence)
    - Optional "allow_drop": permits dropping customers with a penalty
    """

    def solve(
        self,
        fleet: List[Vehicle],
        matrix: MatrixResult,
        depot_index: int = 0,
        demands: Optional[List[int]] = None,
        node_time_windows: Optional[List[Optional[List[int]]]] = None,
        node_service_times: Optional[List[int]] = None,
        pickup_delivery_pairs: Optional[List[PickupDeliveryPair]] = None,
        weights: Optional[dict] = None,
        **kwargs: Any,
    ) -> Routes:

        # ----------------- Basic checks -----------------
        if not matrix or not matrix.distances:
            raise SolverError("OR-Tools: 'matrix.distances' is required.")
        if not fleet:
            raise SolverError("OR-Tools: at least one vehicle is required.")

        # ----------------- Options -----------------
        weights = weights or {}
        w_dist = float(weights.get("distance", 1.0))
        w_time = float(weights.get("time", 0.0))
        vehicle_fixed_cost = float(
            weights.get("vehicle_fixed_cost", 100.0)
        )  # distance-units proxy

        allow_drop = bool(kwargs.get("allow_drop", False))
        drop_penalty = kwargs.get("drop_penalty", None)  # int

        time_limit = int(kwargs.get("time_limit", 60))
        first_solution = str(kwargs.get("first_solution", "PATH_CHEAPEST_ARC")).upper()
        metaheuristic = str(kwargs.get("metaheuristic", "GUIDED_LOCAL_SEARCH")).upper()
        log_search = bool(kwargs.get("log_search", False))

        # Pull optional vehicle TWs from kwargs (or fall back to Vehicle.time_window)
        vtw_input = kwargs.get("vehicle_time_windows", None)
        if vtw_input is None:
            vtw_input = [getattr(v, "time_window", (0, INF)) for v in fleet]

        # ----------------- Normalize node arrays & units -----------------
        norm = _normalize_inputs_for_matrix(
            matrix=matrix,
            depot_index=depot_index,
            demands=demands,
            node_service_times=node_service_times,
            node_time_windows=node_time_windows,
            vehicle_time_windows=vtw_input,
            vehicles_count=len(fleet),
        )

        n = norm["N"]
        depot = norm["depot"]
        demands = norm["demands"]
        service_times = norm["service_times"]
        node_time_windows = norm["node_time_windows"]
        vehicle_time_windows = norm["vehicle_time_windows"]

        durations = matrix.durations  # seconds (or None)

        # ----------------- Build index manager & model -----------------
        starts = [v.start if v.start is not None else depot for v in fleet]
        ends = [v.end if v.end is not None else depot for v in fleet]

        manager = pywrapcp.RoutingIndexManager(n, len(fleet), starts, ends)
        routing = pywrapcp.RoutingModel(manager)

        # ----------------- Transit / cost callbacks -----------------
        COST_SCALE = 1000  # keep arc cost integer

        def cost_callback(from_index: int, to_index: int) -> int:
            i = manager.IndexToNode(from_index)
            j = manager.IndexToNode(to_index)
            d = float(matrix.distances[i][j])
            t_hr = (float(durations[i][j]) / 3600.0) if durations else 0.0
            cost = (w_dist * d) + (w_time * t_hr)
            return int(round(cost * COST_SCALE))

        cost_index = routing.RegisterTransitCallback(cost_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(cost_index)

        # Encourage fewer vehicles (can be overridden via weights.vehicle_fixed_cost)
        routing.SetFixedCostOfAllVehicles(int(round(vehicle_fixed_cost * COST_SCALE)))

        # ----------------- Capacity dimension (only if any demand) -----------------
        if any(int(x) != 0 for x in (demands or [])):
            caps = [
                int(v.capacity[0]) if (v.capacity and len(v.capacity) > 0) else 10**9
                for v in fleet
            ]

            def demand_cb(from_index: int) -> int:
                i = manager.IndexToNode(from_index)
                return int(demands[i])

            demand_index = routing.RegisterUnaryTransitCallback(demand_cb)
            routing.AddDimensionWithVehicleCapacity(
                demand_index,
                0,  # no slack
                caps,
                True,  # start at 0
                "Capacity",
            )

        # ----------------- Time dimension -----------------
        time_dimension = None
        if durations is not None or node_time_windows:
            svc = service_times  # already seconds

            if durations is not None:

                def time_cb(from_index: int, to_index: int) -> int:
                    i = manager.IndexToNode(from_index)
                    j = manager.IndexToNode(to_index)
                    travel = int(round(durations[i][j]))
                    return int(travel + (svc[i] or 0))

            else:
                # No durations: use distances as time units
                def time_cb(from_index: int, to_index: int) -> int:
                    i = manager.IndexToNode(from_index)
                    j = manager.IndexToNode(to_index)
                    travel = int(round(matrix.distances[i][j]))
                    return int(travel + (svc[i] or 0))

            time_index = routing.RegisterTransitCallback(time_cb)

            # horizon: max high end from node TWs, else INF
            horizon = None
            highs = [
                int(b)
                for (a, b) in node_time_windows
                if (a is not None and b is not None)
            ]
            if highs:
                horizon = max(highs)

            routing.AddDimension(
                time_index,
                INF,  # waiting slack allowed
                int(horizon or INF),  # max cumul
                True,  # start cumul at 0
                "Time",
            )
            time_dimension = routing.GetDimensionOrDie("Time")

            # Apply node time windows (seconds)
            for node, (a, b) in enumerate(node_time_windows):
                time_dimension.CumulVar(manager.NodeToIndex(node)).SetRange(
                    int(a), int(b)
                )

            # Apply vehicle time windows (seconds) on starts/ends
            for v_id, (vs, ve) in enumerate(vehicle_time_windows):
                time_dimension.CumulVar(routing.Start(v_id)).SetRange(int(vs), int(ve))
                time_dimension.CumulVar(routing.End(v_id)).SetRange(int(vs), int(ve))

            # Finalizers help feasibility on large VRPTW
            for v_id in range(len(fleet)):
                routing.AddVariableMinimizedByFinalizer(
                    time_dimension.CumulVar(routing.Start(v_id))
                )
                routing.AddVariableMinimizedByFinalizer(
                    time_dimension.CumulVar(routing.End(v_id))
                )

        # ----------------- Pickup & Delivery -----------------
        if pickup_delivery_pairs:
            for pair in pickup_delivery_pairs:
                p_idx = manager.NodeToIndex(int(pair.pickup))
                d_idx = manager.NodeToIndex(int(pair.delivery))
                routing.AddPickupAndDelivery(p_idx, d_idx)
                # same vehicle
                routing.solver().Add(
                    routing.VehicleVar(p_idx) == routing.VehicleVar(d_idx)
                )
                # precedence via time
                if time_dimension is not None:
                    routing.solver().Add(
                        time_dimension.CumulVar(p_idx) <= time_dimension.CumulVar(d_idx)
                    )

        # ----------------- Allow drop (via disjunctions) -----------------
        if allow_drop:
            if drop_penalty is None:
                # robust, very large default – discourages dropping unless truly infeasible
                max_d = max(max(r) for r in matrix.distances)
                max_t = max(max(r) for r in (matrix.durations or matrix.distances))
                est_arc = (w_dist * max_d) + (
                    w_time * (max_t / 3600.0 if matrix.durations else max_t)
                )
                drop_penalty = int(max(10**9, round(est_arc * 10**6)))

            for node in range(n):
                if node == depot:
                    continue
                routing.AddDisjunction([manager.NodeToIndex(node)], int(drop_penalty))

        # ----------------- Search parameters -----------------
        search = pywrapcp.DefaultRoutingSearchParameters()
        # First solution
        fs_map = {
            k: getattr(routing_enums_pb2.FirstSolutionStrategy, k)
            for k in dir(routing_enums_pb2.FirstSolutionStrategy)
            if not k.startswith("_")
        }
        search.first_solution_strategy = fs_map.get(
            first_solution, routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        # Metaheuristic
        mh_map = {
            k: getattr(routing_enums_pb2.LocalSearchMetaheuristic, k)
            for k in dir(routing_enums_pb2.LocalSearchMetaheuristic)
            if not k.startswith("_")
        }
        search.local_search_metaheuristic = mh_map.get(
            metaheuristic,
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH,
        )
        search.time_limit.FromSeconds(int(time_limit))
        if log_search:
            search.log_search = True

        # --- Solve ---
        solution = routing.SolveWithParameters(search)

        # Status
        status_id = routing.status() if hasattr(routing, "status") else None
        status_map = {
            0: "ROUTING_NOT_SOLVED",
            1: "ROUTING_SUCCESS",
            2: "ROUTING_FAIL",
            3: "ROUTING_FAIL_TIMEOUT",
            4: "ROUTING_INVALID",
        }
        status_name = status_map.get(
            status_id,
            (
                "ROUTING_SUCCESS"
                if solution is not None
                else f"UNKNOWN_STATUS_{status_id}"
            ),
        )

        if solution is None:
            raise SolverError(
                f"No feasible solution found. OR-Tools status={status_id} ({status_name})."
            )

        # ----------- Extract routes -----------
        routes: List[Route] = []
        served_customers = set()
        total_km_all, total_sec_all = 0.0, 0.0

        for v_id, veh in enumerate(fleet):
            index = routing.Start(v_id)
            path_nodes: List[int] = []
            total_km = 0.0
            total_sec = 0.0

            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                path_nodes.append(node)

                nxt = solution.Value(routing.NextVar(index))
                if not routing.IsEnd(nxt):
                    i = node
                    j = manager.IndexToNode(nxt)
                    total_km += (
                        float(matrix.distances[i][j]) if matrix.distances else 0.0
                    )
                    if matrix.durations:
                        total_sec += float(matrix.durations[i][j])
                index = nxt

            end_node = manager.IndexToNode(index)
            path_nodes.append(end_node)

            # Count served (exclude depot)
            depot_node = starts[v_id] if isinstance(starts, list) else depot
            for n_node in path_nodes:
                if n_node != depot_node:
                    served_customers.add(n_node)

            # Skip depot-only routes
            only_depot = all(n_node == depot_node for n_node in path_nodes)
            if (
                only_depot
                and total_km == 0
                and (not matrix.durations or total_sec == 0)
            ):
                continue

            total_km_all += total_km
            total_sec_all += total_sec

            routes.append(
                Route(
                    vehicle_id=str(veh.id),
                    waypoint_ids=[str(n) for n in path_nodes],
                    total_distance=total_km,
                    total_duration=int(round(total_sec)) if total_sec else None,
                    emissions=(
                        total_km * float(getattr(veh, "emissions_per_km", 0.0) or 0.0)
                    )
                    or None,
                    metadata={"status": status_name},
                )
            )

        # Dropped = all non-depot nodes that never appear in any route
        all_nodes = set(range(len(matrix.distances or [])))
        maybe_customers = all_nodes - {depot}
        dropped = sorted(maybe_customers - served_customers)

        message = (
            f"status={status_name}; vehicles_used={len(routes)}/{len(fleet)}; "
            f"served={len(served_customers)}/{len(maybe_customers)}; dropped={len(dropped)}; "
            f"total_distance≈{total_km_all:.3f}; total_duration≈{int(round(total_sec_all))}"
        )

        return Routes(status="success", message=message, routes=routes)
