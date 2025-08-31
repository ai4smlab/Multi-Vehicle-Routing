# services/solvers/pyomo_solver.py
from __future__ import annotations
from typing import List, Optional

import pyomo.environ as pyo
from pyomo.opt import SolverFactory

from core.interfaces import VRPSolver
from core.exceptions import SolverError
from models.distance_matrix import MatrixResult
from models.fleet import Vehicle
from models.solvers import Routes, Route


class PyomoSolver(VRPSolver):
    """
    CVRPTW (capacitated VRP with time windows) using a two-index formulation:
      - x[i,j,k] binary arc selection
      - a[i] single arrival time (vehicle-independent)
    Capacity handled as sum of demands per vehicle (CVRP-safe).
    Time windows with Big-M propagation.
    """

    def solve(
        self,
        fleet: List[Vehicle],
        matrix: MatrixResult,
        depot_index: int = 0,
        demands: Optional[List[int]] = None,
        node_time_windows: Optional[List[Optional[List[int]]]] = None,
        node_service_times: Optional[List[int]] = None,
        **kwargs,
    ) -> Routes:
        # --- Basic checks & normalization ---
        if matrix is None or matrix.distances is None:
            raise SolverError("Matrix with distances is required.")

        dist = matrix.distances
        n = len(dist)  # nodes incl. depot
        if n == 0:
            raise SolverError("Empty distance matrix.")

        # durations (seconds) for time windows; default to distance if not provided
        if matrix.durations is not None:
            durations = [[int(round(x)) for x in row] for row in matrix.durations]
        else:
            durations = [[int(round(x)) for x in row] for row in dist]

        m = len(fleet)
        if m == 0:
            raise SolverError("Fleet is empty.")

        # demands
        d = demands or [0] * n
        if len(d) != n:
            raise SolverError("Length of demands must match matrix size.")

        # service times
        s = node_service_times or [0] * n
        if len(s) != n:
            raise SolverError("Length of node_service_times must match matrix size.")

        # time windows
        # default: [0, BIG_T]
        BIG_T = max(
            10_000,
            max((tw[1] for tw in (node_time_windows or []) if tw), default=10_000),
        )
        tw = node_time_windows or [None] * n
        tw_bounds = []
        for i in range(n):
            if tw[i] and len(tw[i]) == 2:
                lo, hi = int(tw[i][0]), int(tw[i][1])
            else:
                lo, hi = 0, BIG_T
            if hi < lo:
                raise SolverError(
                    f"Infeasible time window at node {i}: upper < lower ({hi} < {lo})."
                )
            tw_bounds.append((lo, hi))

        # vehicle capacities
        caps = [int((v.capacity[0] if v.capacity else 10**9)) for v in fleet]

        # --------- Preflight feasibility checks (clear messages) ----------
        total_demand = sum(int(x or 0) for x in d)
        total_capacity = sum(max(0, c) for c in caps)
        if total_demand > total_capacity:
            raise SolverError(
                f"Infeasible: total demand {total_demand} exceeds total vehicle capacity {total_capacity} "
                f"(vehicles={len(fleet)}, capacities={caps}). "
                f"Increase capacity or add vehicles."
            )

        # If any node has a finite latest time that is earlier than the minimum possible arrival,
        # flag it early. We use a cheap lower bound: travel time from depot.
        # (Durations already built above; depot anchored to t=0.)
        for i in range(n):
            lo, hi = tw_bounds[i]
            if i == depot_index:
                continue
            lb_arrival = durations[depot_index][
                i
            ]  # best-case arrival ignoring other customers
            if hi < lb_arrival:
                raise SolverError(
                    f"Infeasible: node {i} latest time {hi} is earlier than shortest travel {lb_arrival} from depot."
                )

        K = range(m)
        N = range(n)
        V = [i for i in range(n) if i != depot_index]  # customers only
        depot = depot_index

        # --- Model ---
        model = pyo.ConcreteModel()

        # Vars
        model.x = pyo.Var(N, N, K, domain=pyo.Binary)  # arc selection

        # single arrival time per node (not per vehicle) to avoid over-constraint
        model.a = pyo.Var(N, bounds=(0, BIG_T), domain=pyo.NonNegativeReals)

        # vehicle usage indicator
        model.used = pyo.Var(K, domain=pyo.Binary)

        # No self loops
        def _no_loops_rule(model, i, j, k):
            return model.x[i, j, k] == 0 if i == j else pyo.Constraint.Skip

        model.no_loops = pyo.Constraint(N, N, K, rule=_no_loops_rule)

        # Each customer visited exactly once (departing arcs across all vehicles)
        def _visit_once_rule(model, i):
            if i == depot:
                return pyo.Constraint.Skip
            return sum(model.x[i, j, k] for j in N for k in K if j != i) == 1

        model.visit_once = pyo.Constraint(V, rule=_visit_once_rule)

        # Each customer has exactly one arrival across all vehicles
        def _arrive_once_rule(model, i):
            if i == depot:
                return pyo.Constraint.Skip
            return sum(model.x[j, i, k] for j in N for k in K if j != i) == 1

        model.arrive_once = pyo.Constraint(V, rule=_arrive_once_rule)

        # Start/end at depot exactly when vehicle is used
        def _start_rule(model, k):
            return sum(model.x[depot, j, k] for j in N if j != depot) == model.used[k]

        model.depot_start = pyo.Constraint(K, rule=_start_rule)

        def _end_rule(model, k):
            return sum(model.x[i, depot, k] for i in N if i != depot) == model.used[k]

        model.depot_end = pyo.Constraint(K, rule=_end_rule)

        # Flow conservation for each vehicle
        def _flow_rule(model, i, k):
            if i == depot:
                return pyo.Constraint.Skip
            return (
                sum(model.x[i, j, k] for j in N if j != i)
                - sum(model.x[j, i, k] for j in N if j != i)
                == 0
            )

        model.flow = pyo.Constraint(V, K, rule=_flow_rule)

        # If a vehicle is not used, it cannot touch any customer (link arcs → used[k])
        def _link_out_rule(model, i, k):
            if i == depot:
                return pyo.Constraint.Skip
            return sum(model.x[i, j, k] for j in N if j != i) <= model.used[k]

        model.link_out = pyo.Constraint(V, K, rule=_link_out_rule)

        def _link_in_rule(model, i, k):
            if i == depot:
                return pyo.Constraint.Skip
            return sum(model.x[j, i, k] for j in N if j != i) <= model.used[k]

        model.link_in = pyo.Constraint(V, K, rule=_link_in_rule)

        # If a vehicle is used, it must serve at least one customer (prevents a depot-only tour)
        def _used_has_work_rule(model, k):
            return (
                sum(model.x[i, j, k] for i in V for j in N if j != i) >= model.used[k]
            )

        model.used_has_work = pyo.Constraint(K, rule=_used_has_work_rule)

        # Time windows
        # Anchor depot time to 0
        model.depot_time_anchor = pyo.Constraint(expr=model.a[depot] == 0)

        # Node-wise bounds
        def _tw_bounds_rule(model, i):
            lo, hi = tw_bounds[i]
            return pyo.inequality(lo, model.a[i], hi)

        model.tw_bounds = pyo.Constraint(N, rule=_tw_bounds_rule)

        # Time propagation with Big-M
        # a[j] >= a[i] + s[i] + t[i][j] - M*(1 - x[i,j,k])
        M = BIG_T + max((max(row) for row in durations), default=0) + max(s) + 1

        def _time_prop_rule(model, i, j, k):
            # skip self arcs
            if i == j:
                return pyo.Constraint.Skip
            # IMPORTANT: do NOT constrain arrival time into depot, because a[depot] is fixed to 0.
            # Enforcing a[depot] >= a[i] + ... would be infeasible whenever any route returns.
            if j == depot:
                return pyo.Constraint.Skip
            # allow propagation from depot -> j and all customer -> customer arcs
            return model.a[j] >= model.a[i] + s[i] + durations[i][j] - M * (
                1 - model.x[i, j, k]
            )

        model.time_prop = pyo.Constraint(N, N, K, rule=_time_prop_rule)

        # Capacity: sum of demands served by vehicle k ≤ capacity[k]
        def _cap_rule(model, k):
            # if vehicle k visits i, then exactly one outgoing arc from i by k => sum_j x[i,j,k] ∈ {0,1}
            return (
                sum(d[i] * sum(model.x[i, j, k] for j in N if j != i) for i in V)
                <= caps[k]
            )

        model.capacity = pyo.Constraint(K, rule=_cap_rule)

        # ---- Objective (build expr first; set obj once) ----
        vehicle_fixed_cost = float(kwargs.get("vehicle_fixed_cost", 0.0))
        distance_cost = sum(
            dist[i][j] * model.x[i, j, k] for i in N for j in N for k in K if i != j
        )

        obj_expr = distance_cost
        if vehicle_fixed_cost > 0:
            # use the explicit vehicle usage indicator
            used_vehicles = sum(model.used[k] for k in K)
            obj_expr = distance_cost + vehicle_fixed_cost * used_vehicles

        model.obj = pyo.Objective(expr=obj_expr, sense=pyo.minimize)

        # --- Solve ---
        solver = SolverFactory("cbc")
        if solver is None:
            raise SolverError("CBC solver not found by Pyomo.")

        # Give the solver more room by default on larger instances
        default_tlim = int(kwargs.get("time_limit", 900 if n >= 80 else 60))
        results = solver.solve(
            model,
            tee=False,
            options={
                "seconds": default_tlim,
                "ratioGap": float(kwargs.get("ratioGap", 0.0)),
            },
        )

        # -------- Robust termination checks (soft vs hard) --------
        from pyomo.opt import SolverStatus as SS, TerminationCondition as TC

        status = results.solver.status
        term = results.solver.termination_condition
        status_s = str(status).lower()
        term_s = str(term).lower()

        # Terms that mean "stopped early / mid-search"
        soft_terms = {
            getattr(TC, "maxTimeLimit", None),
            getattr(TC, "maxIterations", None),
            getattr(TC, "intermediateNonInteger", None),
        }
        soft_terms = {t for t in soft_terms if t is not None}

        ok_terms = {TC.optimal}
        if hasattr(TC, "feasible"):
            ok_terms.add(TC.feasible)

        # Decide
        if status == SS.ok and term in ok_terms:
            pass  # proceed to extract
        elif (
            status in {SS.aborted, SS.warning}
            and (term in soft_terms or "intermediate" in term_s or "time" in term_s)
        ) or ("aborted" in status_s and "intermediate" in term_s):
            # Soft stop: try extracting an incumbent; if none, we’ll raise a helpful msg after extraction.
            pass
        elif term == TC.infeasible or "infeasible" in term_s:
            raise SolverError(
                "Infeasible model: constraints admit no solution with the given fleet/capacity/time windows."
            )
        else:
            # Unknown/real error
            raise SolverError(f"Pyomo/CBC error (status={status}, term={term})")

        # --- Extract solution into Routes ---
        routes_out: List[Route] = []

        # Build adjacency per vehicle
        for k_idx, veh in enumerate(fleet):
            next_of = {}
            used = False
            for i in N:
                for j in N:
                    if i == j:
                        continue
                    if pyo.value(model.x[i, j, k_idx]) > 0.5:
                        next_of[i] = j
                        used = True

            if not used:
                continue

            # Follow path starting at depot
            path = [depot]
            total_dist = 0.0
            seen = {depot}
            cur = depot
            max_steps = n + 5
            steps = 0
            while cur in next_of and steps < max_steps:
                nxt = next_of[cur]
                total_dist += float(dist[cur][nxt])
                path.append(nxt)
                if nxt == depot:
                    break
                if nxt in seen:
                    break
                seen.add(nxt)
                cur = nxt
                steps += 1

            if len(path) <= 2 or total_dist <= 1e-6:
                continue

            routes_out.append(
                Route(
                    vehicle_id=veh.id,
                    waypoint_ids=[str(i) for i in path],
                    total_distance=total_dist,
                    total_duration=None,
                    emissions=None,
                    metadata={"solver": "cbc"},
                )
            )

        # ---- post-extraction guard ----
        from pyomo.opt import (
            SolverStatus as SS,
            TerminationCondition as TC,
        )  # reuse the ones you imported above

        if not routes_out:
            # Soft-stop: time/iterations/intermediate-non-integer -> suggest more time or relaxation
            status = results.solver.status
            term = results.solver.termination_condition
            status_s = str(status).lower()
            term_s = str(term).lower()

            soft_terms = {
                getattr(TC, "maxTimeLimit", None),
                getattr(TC, "maxIterations", None),
                getattr(TC, "intermediateNonInteger", None),
            }
            soft_terms = {t for t in soft_terms if t is not None}

            if (
                status in {SS.aborted, SS.warning}
                and (term in soft_terms or "intermediate" in term_s or "time" in term_s)
            ) or ("aborted" in status_s and "intermediate" in term_s):
                raise SolverError(
                    "Solver stopped before finding an integer-feasible solution. "
                    "Try increasing time_limit (e.g., 180–300s) or relaxing time windows/capacity."
                )

            raise SolverError(
                "No usable routes found. This often means time windows are too tight or capacities too low."
            )

        return Routes(status="success", message="Solution found", routes=routes_out)
