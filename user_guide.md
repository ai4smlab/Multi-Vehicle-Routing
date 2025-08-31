# User Manual

## What’s here

- **Map (MapLibre)** with waypoint editing and layers
- **Solvers**: OR-Tools, Pyomo (optional), VROOM, Mapbox Optimizer (optional)
- **Distance matrix adapters**: haversine, euclidean (local), osm_graph, openrouteservice, mapbox, google
- **Datasets**: Solomon, VRPLIB, custom CSV/GeoJSON
- **OSM POIs**: search by place or by drawn bbox

## Backend API (Swagger)

Open **http://localhost:8000/docs** for interactive docs. Key endpoints:

- `POST /solver` – run a VRP solver
- `POST /distance-matrix` – get a matrix from an adapter
- `GET /benchmarks/files` / `GET /benchmarks/load` – list/load benchmark instances
- `GET /osm/pois/auto` – OSM POIs by **place** or **bbox**

### Handy cURL

**Distance matrix (haversine)**
```bash
curl -sS -X POST http://localhost:8000/distance-matrix -H 'content-type: application/json' -d '{
  "adapter": "haversine",
  "mode": "driving",
  "parameters": { "metrics": ["distance","duration"], "units": "m" },
  "origins":      [{"lon":2.29,"lat":48.86},{"lon":2.33,"lat":48.85}],
  "destinations": [{"lon":2.29,"lat":48.86},{"lon":2.33,"lat":48.85}]
}'
```

**OSM POIs (place)**
```bash
curl -sS -G 'http://localhost:8000/osm/pois/auto' \
  --data-urlencode 'place=Paris, France' \
  --data-urlencode 'key=amenity' \
  --data-urlencode 'value=restaurant|cafe' \
  --data-urlencode 'include_ways=true' \
  --data-urlencode 'include_relations=true' \
  --data-urlencode 'limit=300'
```

**OSM POIs (bbox)**
```bash
curl -sS -G 'http://localhost:8000/osm/pois/auto' \
  --data-urlencode 'south=48.80' \
  --data-urlencode 'west=2.25' \
  --data-urlencode 'north=48.90' \
  --data-urlencode 'east=2.42' \
  --data-urlencode 'key=amenity' \
  --data-urlencode 'value=restaurant|cafe' \
  --data-urlencode 'limit=300'
```

**Solve – OR-Tools (TSP)**
```bash
curl -sS -X POST http://localhost:8000/solver -H 'content-type: application/json' -d '{
  "solver": "ortools",
  "depot_index": 0,
  "fleet": [{"id":"veh-1","start":0,"end":0,"capacity":[999999]}],
  "weights": {"distance":1,"time":0},
  "matrix": {
    "distances": [[0,1,1.5],[1,0,1.2],[1.5,1.2,0]],
    "durations": [[0,60,90],[60,0,72],[90,72,0]]
  }
}'
```

## Frontend (http://localhost:3000)

### Main pages
- `/map/maplibre` – Primary UI
- `/map/mapbox`, `/map/googlemaps` – alternates (optional)

### Panels & what they do

- **Waypoint Sidebar**: add/remove points, set depot, edit demand/Service/TW.
- **Solver Panel / Solve Button**: choose solver & adapter; Solve and add a result to the right panel.
- **Result Summary Panel**: solution metrics, per-vehicle routes, export.
- **Route Tools Panel**: ETA show/hide/clear for the active route; export helpers.
- **Benchmark Selector**: load a Solomon/VRPLIB instance, auto-choose adapter (euclidean for planar), solve & compare to best-known.
- **Real-World Dataset (OSM POIs)**:
  - Mode **Place** or **BBox** (you can draw a bbox on the map).
  - Key/Value (regex allowed like `restaurant|cafe`).
  - Load results as a layer, toggle visibility, save datasets, clear all.

### Keyboard/Mouse tips
- Click on the map to add a waypoint (if enabled).
- Right-click for context menu (zoom/clear).
- Use the **Draw BBox** toggle in RWD panel, then drag on the map.

## Data & Units (important)

- **Matrices**:
  - `distances` in **meters** (or arbitrary “km-ish” for euclidean).
  - `durations` in **seconds**.
- **Service times / Time windows**: **seconds** end-to-end in the payload.
- **Capacity/Demands**: unitless; just be consistent (Solomon uses integers).

## Troubleshooting

- **OR-Tools “ROUTING_INVALID”**:
  - Check durations are **seconds**, not minutes.
  - Depot time window wide (0 to large).
  - If TW too tight, allow waiting slack (we already do) and make service times realistic.
  - Ensure vehicle capacity ≥ total demand served.
- **VROOM “delivery length 0 instead of 1”**:
  - Our wrapper avoids deliveries when not requested; use current backend (fixed).
- **Distance matrix errors “origins required”**:
  - `osm_graph` uses `coordinates: [{lon,lat}...]`; others use `origins[]/destinations[]`.
- **Overpass 400 / 0 features**:
  - Try bbox mode; reduce `limit`; avoid nested quotes (backend auto-normalizes regex).
- **CORS**: set `CORS_ORIGINS=http://localhost:3000` and restart backend.
