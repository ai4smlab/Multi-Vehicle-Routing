# services/solver_factory.py
from typing import Dict, Callable, List
from core.interfaces import VRPSolver

_solver_registry: Dict[str, Callable[[], VRPSolver]] = {}
_registered = False


def register_solver(name: str, ctor: Callable[[], VRPSolver]) -> None:
    key = name.lower().strip()
    if key in _solver_registry:
        raise ValueError(f"Solver '{name}' is already registered.")
    _solver_registry[key] = ctor


def get_solver(name: str) -> VRPSolver:
    key = name.lower().strip()
    # Lazy init in case app lifespan didn't run
    if key not in _solver_registry:
        register_solvers()
    if key not in _solver_registry:
        raise ValueError(f"Solver '{name}' is not registered.")
    return _solver_registry[key]()


def list_solvers() -> List[str]:
    # <—— ensure the built-ins are registered before listing
    if not _solver_registry:
        register_solvers()
    return sorted(_solver_registry.keys())


def register_solvers() -> None:
    """Call once at startup/tests to register built-ins."""
    global _registered
    if _registered:
        return
    # Late imports to avoid heavy deps on import
    from services.solvers.ortools_solver import OrToolsSolver
    from services.solvers.vroom_solver import VroomSolver
    from services.solvers.pyomo_solver import PyomoSolver

    register_solver("ortools", OrToolsSolver)
    register_solver("vroom", VroomSolver)
    register_solver("pyomo", PyomoSolver)

    _registered = True
