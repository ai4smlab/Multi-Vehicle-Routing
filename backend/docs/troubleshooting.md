# Troubleshooting

## "Solver 'ortools' is not registered"
- Ensure `load_plugins()` is called (wired in `main.py` lifespan).
- In tests, use the shared `client` fixture that bootstraps the app, not a raw `TestClient(app)` without plugins.

## OR-Tools "CP Solver fail"
- Check matrix shape is **square** and >= 2.
- Verify `fleet` has at least one vehicle and `depot_index` in bounds.
- Inspect time windows and service times; infeasible windows cause failures.

## Pyomo "aborted" with solution
- CBC may return a partial incumbent; the backend extracts arcs and still returns feasible routes.
- Increase time or relax tolerances if needed.

## VROOM wrapper variations
- Some builds require coordinates only. The backend auto-detects and either uses `set_costs` or falls back to a NN heuristic.