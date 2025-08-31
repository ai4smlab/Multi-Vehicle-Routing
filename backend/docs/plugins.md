# Plugin System (Adapters & Solvers)

## Registration
`core/load_plugins.load_plugins()` calls:
- `register_adapters()` → registers **haversine**, **openrouteservice**, **google**.
- `services.solver_factory.register_solvers()` → registers **ortools**, **pyomo**, **vroom**.

Adapters are created through `AdapterFactoryRegistry.get(name)`;  
Solvers are instantiated via `SolverFactory.get_solver(name)`.

## Adding a New Solver
1. Implement `class MySolver(VRPSolver)` with `solve(...) -> Routes`.
2. Register in `register_solvers()`:
   ```python
   from services.solvers.my_solver import MySolver
   register_solver("mysolver", MySolver)
   ```
3. Call `load_plugins()` at startup (already wired in `main.py`).

## Adding a New Adapter
1. Implement `class MyAdapter(DistanceMatrixAdapter)`.
2. Register in `register_adapters()`:
   ```python
   AdapterFactoryRegistry.register("myadapter", lambda: MyAdapter(...))
   ```