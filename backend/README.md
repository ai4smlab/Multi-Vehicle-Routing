# VRP Backend (FastAPI)

A modular backend for Vehicle Routing Problems (VRP): distance‑matrix adapters, multiple solvers (OR‑Tools, Pyomo, VROOM), dataset loaders (Solomon, VRP‑Set‑XML100), and handy endpoints for benchmarks, geometry, and emissions.

## TL;DR

```bash
# 1) Install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2) (optional) set keys for online adapters
export ORS_API_KEY="<your-openrouteservice-key>"

# 3) Run the API
uvicorn main:app --reload

# 4) Open
# http://127.0.0.1:8000/docs
```

## Features

- **Adapters:** `haversine` (offline), `openrouteservice` (online), Google (optional), `osm_graph` (planned).
- **Solvers:** `ortools` (CVRP/VRPTW/PD), `pyomo` (CVRP/VRPTW via CBC), `vroom` (index/coord modes with graceful fallback).
- **Geometry:** `/route/geometry` (Mapbox/OSRM providers) to build snapped display geometry.
- **Datasets:** Solomon .txt, VRP‑Set‑XML100 .xml, CSV/GeoJSON helpers.
- **Benchmarks:** browse, load instances; pair instance/solution when available.
- **Emissions:** simple CO₂e estimation hooks & route enrichment.
- **Plugin system:** one place to register new adapters/solvers.
- **Tests:** pytest suite with optional heavier benchmarks.

## Architecture at a glance

High‑level diagrams live in `backend/doc/architecture.md`.

### Request flow

- `POST /distance-matrix` → adapter computes distances (`durations` if available).
- `POST /solver` → solver builds routes from matrix + constraints.
- `POST /route/geometry` → reconstruct snapped LineString (for map rendering, ETA/trips, and traffic gradient).
- Optional enrichment (distance/duration/emissions) is applied before returning to the client.

## Running

**Requirements**
- Python 3.10+
- OR‑Tools (via pip)
- Pyomo + CBC on PATH (or GLPK alternative)
- VROOM optional; when not present, the backend’s VROOM wrapper falls back to a nearest‑neighbor heuristic.

**Environment variables**
- `DATA_DIR` – datasets root (default `./backend/data`)
- `ORS_API_KEY` – for OpenRouteService adapter
- Optional: `GOOGLE_MAPS_API_KEY`, provider tokens for geometry proxies (if used)

## Endpoints (overview)

- `POST /distance-matrix` — compute a matrix via adapter
- `POST /solver` — solve a VRP via solver (ortools, pyomo, vroom)
- `POST /route/geometry` — snap/reconstruct LineString (provider: mapbox/osrm)
- `POST /mapbox/optimize` — proxy to Mapbox Optimization
- `POST /mapbox/match` — proxy to Mapbox Map Matching
- **Files / Datasets**
  - `GET /files` — list/browse
  - `POST /files/upload` — upload custom dataset files (CSV/GeoJSON/Solomon/XML)
  - `DELETE /files/{path}` — delete uploaded file
  - `GET /benchmarks`, `GET /benchmarks/files`, `GET /benchmarks/load`, `GET /benchmarks/find`
- `POST /emissions/estimate`
- `GET /status`

Open Swagger at **/docs** for full schemas.

## API examples

**1) Distance matrix (offline haversine)**
```bash
curl -X POST http://127.0.0.1:8000/distance-matrix   -H "content-type: application/json"   -d '{
    "adapter": "haversine",
    "origins": [{"lat":37.7749,"lon":-122.4194},{"lat":34.0522,"lon":-118.2437}],
    "destinations": [{"lat":36.1699,"lon":-115.1398}],
    "mode": "driving"
}'
```

**2) Solve (OR‑Tools, index mode)**
```bash
curl -X POST http://127.0.0.1:8000/solver   -H "content-type: application/json"   -d '{
    "solver": "ortools",
    "matrix": { "distances": [[0,5,4],[5,0,3],[4,3,0]] },
    "fleet": [{ "id":"veh-1", "capacity":[999], "start":0, "end":0 }],
    "depot_index": 0,
    "demands": [0,3,4],
    "node_service_times": [0,0,0]
  }'
```

**3) Solve (VROOM, coordinate mode)**
```bash
curl -X POST http://127.0.0.1:8000/solver   -H "content-type: application/json"   -d '{
    "solver": "vroom",
    "coordinates": [[-122.4194,37.7749],[-118.2437,34.0522],[-115.1398,36.1699]],
    "fleet": [{ "id":"veh-1", "capacity":[999], "start":0, "end":0 }],
    "depot_index": 0
  }'
```

**4) Load a benchmark instance**
```bash
curl "http://127.0.0.1:8000/benchmarks/load?dataset=solomon&name=C101"
```

## Datasets & Benchmarks

`/benchmarks` enumerates datasets under `DATA_DIR` (`backend/data` by default). Supported loaders unify shape to a canonical schema (`waypoints`, `fleet`, `matrix`, `meta`).

## Files & Custom Datasets (Design)

The UI can POST uploads to `/files/upload`, browse via `/files`, delete with `DELETE /files/{path}`, and then load & solve by calling `/solver` with the normalized payload.

## Development

See `backend/doc/development.md` for IDE tips and pytest commands.

## Troubleshooting (quick)

- “solver not registered” → ensure `load_plugins()` runs (wired in `main.py` lifespan)
- OR‑Tools failure → check matrix is square and depot index valid
- Pyomo infeasible → loosen time windows / capacity
- VROOM schema errors → ensure `demand` is a **list**; `time_window` is an **object** `{start,end}`