# Datasets & Loaders

## Supported
- **Solomon** (TXT) — parsed by `file_handler/solomon_loader.py`
- **VRP-Set-XML100** (XML) — robust loader in `file_handler/vrplib_lib_wrapper.py` + `services/file_handler/xml_loader.py`
- Simple CSV/GeoJSON point loaders (opt‑in) in `services/file_loader/`

## Shape
Loaders unify into:
```json
{
  "waypoints": [{ "id": "0", "lat": 40, "lon": 50, "demand": 0, "service_time": 0, "time_window": [0, 3600], "depot": true }, ...],
  "fleet": { "vehicles": [ { "id": "veh-1", "capacity": [200], "start": 0, "end": 0 }, ... ] },
  "depot_index": 0,
  "matrix": { "distances": [[...]], "durations": [[...]] } | null,
  "meta": { ... }
}
```

## Index & Files
- `file_handler/dataset_indexer.py` enumerates datasets, supports search/paging, and pairing instance/solution files.
