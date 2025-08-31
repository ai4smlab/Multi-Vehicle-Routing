# services/bootstrap.py
def load_plugins() -> None:
    # Solvers
    from services.solver_factory import register_solver

    try:
        from services.solvers.ortools_solver import OrToolsSolver

        register_solver("ortools", OrToolsSolver)
    except Exception:
        pass

    try:
        from services.solvers.vroom_solver import VroomSolver

        register_solver("vroom", VroomSolver)
    except Exception:
        pass

    try:
        from services.solvers.pyomo_solver import PyomoSolver

        register_solver("pyomo", PyomoSolver)
    except Exception:
        pass

    # Adapters
    from adapters.adapter_factory import create_adapter

    try:
        from adapters.offline.haversine_adapter import HaversineAdapter

        create_adapter("haversine", HaversineAdapter)
    except Exception:
        pass

    try:
        from adapters.online.openrouteservice_adapter import ORSDistanceMatrixAdapter

        create_adapter("openrouteservice", ORSDistanceMatrixAdapter)
    except Exception:
        pass

    # If you have google/google_routes adapters:
    try:
        from adapters.online.google_matrix_adapter import GoogleMatrixAdapter

        create_adapter("google", GoogleMatrixAdapter)
    except Exception:
        pass

    try:
        from adapters.online.google_routes_adapter import GoogleRoutesAdapter

        create_adapter("google_routes", GoogleRoutesAdapter)
    except Exception:
        pass
