# file_handler/solomon_loader.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import math
import re

SECONDS_PER_MIN = 60


def _euclid_mtx(coords: List[Tuple[float, float]]) -> List[List[float]]:
    n = len(coords)
    mtx = [[0.0] * n for _ in range(n)]
    for i in range(n):
        xi, yi = coords[i]
        for j in range(i + 1, n):
            xj, yj = coords[j]
            d = math.hypot(xi - xj, yi - yj)
            mtx[i][j] = d
            mtx[j][i] = d
    return mtx


def _find_vehicle_block(lines: List[str]) -> Tuple[int, int]:
    veh, cap = None, None
    for i, ln in enumerate(lines[:60]):
        if re.search(r"\bVEHICLES?\b", ln, re.I) or re.search(r"\bVEHICLE\b", ln, re.I):
            for j in range(i, min(i + 12, len(lines))):
                row = lines[j]
                nums = re.findall(r"-?\d+(?:\.\d+)?", row)
                if len(nums) >= 2:
                    try:
                        veh = int(float(nums[0]))
                        cap = int(float(nums[1]))
                        break
                    except Exception:
                        pass
            break
    if veh is None or veh <= 0:
        veh = 10
    if cap is None or cap <= 0:
        cap = 200
    return veh, cap


def _find_data_start(lines: List[str]) -> Optional[int]:
    for i, ln in enumerate(lines):
        u = ln.upper()
        if u.startswith("CUSTOMER"):
            k = i + 1
            while k < len(lines) and not lines[k].strip():
                k += 1
            if k < len(lines) and re.search(r"CUST\s*NO\.", lines[k], re.I):
                return k + 1
        if re.search(r"CUST\s*NO\.", ln, re.I) and re.search(r"XCOORD", ln, re.I):
            return i + 1
    return None


def load_solomon_txt(path: str | Path, compute_matrix: bool = True) -> Dict[str, Any]:
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="ignore")
    lines_raw = text.splitlines()
    lines = [ln.rstrip("\r\n") for ln in lines_raw]

    vehicles, capacity = _find_vehicle_block(lines)
    start = _find_data_start(lines)

    rows: List[Dict[str, Any]] = []
    if start is not None:
        for ln in lines[start:]:
            if not ln.strip():
                continue
            nums = re.findall(r"-?\d+(?:\.\d+)?", ln)
            if len(nums) < 7:
                continue
            cid, x, y, dem, ready, due, service = nums[:7]
            try:
                rows.append(
                    {
                        "id": int(float(cid)),
                        "x": float(x),
                        "y": float(y),
                        "demand": int(float(dem)),
                        "ready": int(float(ready)),
                        "due": int(float(due)),
                        "service": int(float(service)),
                    }
                )
            except Exception:
                continue

    if not rows:
        head = [ln.strip() for ln in lines[:8]]
        raise ValueError(
            f"Solomon parser: no rows parsed from {p}. " f"Header? -> {head}"
        )

    max_id = max(r["id"] for r in rows)
    n = max_id + 1
    coords = [(0.0, 0.0)] * n
    demands = [0] * n
    ready = [0] * n
    due = [10**9] * n
    service = [0] * n

    for r in rows:
        i = r["id"]
        if 0 <= i < n:
            coords[i] = (r["x"], r["y"])
            demands[i] = r["demand"]
            ready[i] = r["ready"]
            due[i] = max(ready[i], r["due"])
            service[i] = r["service"]

    depot_index = (
        0
        if any(r["id"] == 0 for r in rows)
        else (min(r["id"] for r in rows) if rows else 0)
    )
    max_due = max(due) if due else 10**9
    if 0 <= depot_index < n:
        ready[depot_index] = min(ready[depot_index], 0)
        due[depot_index] = max(due[depot_index], max_due)

    # 👇 Keep both spaces: solver-space (x,y) and legacy lat/lon fields
    waypoints: List[Dict[str, Any]] = []
    for i, (x, y) in enumerate(coords):
        waypoints.append(
            {
                "id": str(i),
                # solver space
                "x": float(x),
                "y": float(y),
                # legacy planar-as-lat/lon (kept for backward compatibility)
                "lat": float(x),
                "lon": float(y),
                "demand": int(demands[i]),
                "service_time": int(service[i]) * SECONDS_PER_MIN,
                "time_window": [
                    int(ready[i]) * SECONDS_PER_MIN,
                    int(due[i]) * SECONDS_PER_MIN,
                ],
                "depot": (i == depot_index),
            }
        )

    vehicles_list = [
        {
            "id": f"veh-{k+1}",
            "start": depot_index,
            "end": depot_index,
            "capacity": [int(capacity)],
            "skills": [],
            "time_window": None,
            "max_distance": None,
            "max_duration": None,
            "speed": None,
            "emissions_per_km": None,
        }
        for k in range(max(1, int(vehicles)))
    ]

    matrix = None
    if compute_matrix and n > 0:
        distances = _euclid_mtx([(float(x), float(y)) for (x, y) in coords])
        durations = [[int(round(d * 60)) for d in row] for row in distances]
        matrix = {"distances": distances, "durations": durations}

    return {
        "edge_weight_type": "EUC_2D",
        "coordinate_spaces": {
            "solver": {"type": "euclidean", "fields": ["x", "y"]},
            "display": {
                "type": "wgs84",
                "fields": ["lon", "lat"],
            },  # will be filled by /benchmarks/load?include_display=true
        },
        "waypoints": waypoints,
        "fleet": {"vehicles": vehicles_list},
        "depot_index": depot_index,
        "matrix": matrix,
        "meta": {
            "source": str(p),
            "format": "solomon_txt",
            "capacity": int(capacity),
            "vehicles": int(vehicles),
        },
    }
