# API Reference

Base URL: `/`

## Distance Matrix
`POST /distance-matrix`  
Request depends on adapter (haversine/openrouteservice/google). Returns `{ matrix: MatrixResult }`.

## Solver
`POST /solver`  
Body: `SolveRequest`  
Returns: `{ status, message, data: Routes }`

Notes:
- `ortools` and `pyomo`: require `matrix.distances` (and optionally `durations`).
- `vroom`: supports matrix **or** coordinates (when the local VROOM wrapper is coord‑only). The backend auto‑detects and falls back to a NN heuristic.

## Benchmarks
- `GET /benchmarks` — list datasets.
- `GET /benchmarks/files?dataset=...&q=...&limit=&offset=` — list/search files.
- `GET /benchmarks/load?dataset=...&name=...` — parse instance into canonical schema.
- `GET /benchmarks/find?dataset=...&name=...` — find matching instance/solution pair.

## Emissions
- `POST /emissions/estimate` — simple CO₂ estimate.

## Status
- `GET /status` — healthcheck.
