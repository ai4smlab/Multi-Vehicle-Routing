# file_handler/vrplib_loader.py
from __future__ import annotations
import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------- helpers ----------------


def _euclidean(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    dx = p1[0] - p2[0]
    dy = p1[1] - p2[1]
    return math.hypot(dx, dy)


def _build_distance_matrix_xy(coords: List[Tuple[float, float]]) -> List[List[float]]:
    n = len(coords)
    mtx = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = _euclidean(coords[i], coords[j])
            mtx[i][j] = d
            mtx[j][i] = d
    return mtx


def _tokenize_lines(text: str) -> List[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _read_sections(lines: List[str]) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {}
    current = None
    for ln in lines:
        upper = ln.upper()
        if upper.endswith("_SECTION") or upper in (
            "NODE_COORD_SECTION",
            "DEMAND_SECTION",
            "DEPOT_SECTION",
        ):
            current = upper
            sections[current] = []
        elif upper.startswith("SERVICE_TIME"):
            current = "SERVICE_TIME_SECTION"
            sections[current] = []
        elif upper.startswith("TIME_WINDOW"):
            current = "TIME_WINDOW_SECTION"
            sections[current] = []
        elif upper.startswith("EOF"):
            break
        elif current:
            sections[current].append(ln)
    return sections


def _parse_vehicle_header(lines: List[str]) -> Tuple[int, int]:
    num = None
    cap = None
    txt = "\n".join(lines).upper()

    m = re.search(r"\bVEHICLE\b.*?NUMBER\s+CAPACITY\s+(\d+)\s+(\d+)", txt, re.S)
    if m:
        num = int(m.group(1))
        cap = int(m.group(2))

    if cap is None:
        m2 = re.search(r"CAPACITY\s*:\s*(\d+)", txt)
        if m2:
            cap = int(m2.group(1))
        m3 = re.search(r"VEHICLES?\s*:\s*(\d+)", txt)
        if m3:
            num = int(m3.group(1))

    if num is None or cap is None:
        try:
            for i, ln in enumerate(lines):
                if ln.strip().upper() == "VEHICLE":
                    for j in range(i + 1, min(i + 8, len(lines))):
                        s = lines[j].strip()
                        if not s:
                            continue
                        up = s.upper().replace(" ", "")
                        if up.startswith("NUMBER") or "CAPACITY" in up:
                            continue
                        parts = s.split()
                        if (
                            len(parts) >= 2
                            and parts[0].isdigit()
                            and parts[1].isdigit()
                        ):
                            if num is None:
                                num = int(parts[0])
                            if cap is None:
                                cap = int(parts[1])
                            raise StopIteration
        except StopIteration:
            pass

    if num is None:
        num = 1
    if cap is None:
        cap = 10**9
    return num, cap


def _parse_edge_weight_type(lines: List[str]) -> Optional[str]:
    for ln in lines[:100]:
        m = re.search(r"EDGE_WEIGHT_TYPE\s*:\s*([A-Za-z0-9_]+)", ln, re.I)
        if m:
            return m.group(1).upper()
    return None


def _parse_node_coord_section(lines: List[str]) -> List[Tuple[int, float, float]]:
    nodes: List[Tuple[int, float, float]] = []
    for ln in lines:
        parts = ln.split()
        if len(parts) >= 3 and parts[0].isdigit():
            i = int(parts[0])
            x = float(parts[1])
            y = float(parts[2])
            nodes.append((i, x, y))
    return nodes


def _parse_demand_section(lines: List[str]) -> Dict[int, int]:
    demands: Dict[int, int] = {}
    for ln in lines:
        parts = ln.split()
        if len(parts) >= 2 and parts[0].isdigit():
            idx = int(parts[0])
            dem = int(float(parts[1]))
            demands[idx] = dem
    return demands


def _parse_time_window_section(lines: List[str]) -> Dict[int, Tuple[int, int]]:
    tw: Dict[int, Tuple[int, int]] = {}
    for ln in lines:
        parts = ln.split()
        if len(parts) >= 3 and parts[0].isdigit():
            idx = int(parts[0])
            start = int(float(parts[1]))
            end = int(float(parts[2]))
            tw[idx] = (start, end)
    return tw


def _parse_service_time_section(lines: List[str]) -> Dict[int, int]:
    st: Dict[int, int] = {}
    for ln in lines:
        parts = ln.split()
        if len(parts) >= 2 and parts[0].isdigit():
            idx = int(parts[0])
            sv = int(float(parts[1]))
            st[idx] = sv
    return st


def _parse_depot_section(lines: List[str]) -> List[int]:
    depots: List[int] = []
    for ln in lines:
        ln = ln.strip()
        if ln == "-1":
            break
        if ln and ln.lstrip("+-").isdigit():
            depots.append(int(ln))
    return depots


def _is_solomon_text(contents: str) -> bool:
    up = contents.upper()
    return ("CUST" in up and "XCOORD" in up and "YCOORD" in up) or "CUSTOMER" in up


# -------- Solomon parser (classic Solomon .txt like c101.txt) --------


def _parse_solomon_text(contents: str) -> Dict[str, any]:
    lines = _tokenize_lines(contents)
    txt_up = "\n".join(lines).upper()

    veh = 1
    cap = 10**9
    m = re.search(r"VEHICLE\s+NUMBER\s+CAPACITY\s*\n\s*(\d+)\s+(\d+)", txt_up, re.S)
    if m:
        veh = int(m.group(1))
        cap = int(m.group(2))

    header_idx = None
    for i, ln in enumerate(lines):
        up = ln.upper()
        if "CUST" in up and "XCOORD" in up and "YCOORD" in up and "DEMAND" in up:
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("Solomon: header line not found")

    rows = lines[header_idx + 1 :]
    waypoints: List[Dict] = []
    depot_index = 0
    ids = []

    for i, ln in enumerate(rows):
        parts = ln.split()
        if len(parts) < 7:
            continue
        try:
            cid = int(parts[0])
            x = float(parts[1])
            y = float(parts[2])
            dem = int(float(parts[3]))
            ready = int(float(parts[4]))
            due = int(float(parts[5]))
            service = int(float(parts[6]))
        except Exception:
            continue

        ids.append(cid)
        waypoints.append(
            {
                "id": str(cid),
                # keep both spaces
                "x": x,
                "y": y,
                "lat": x,
                "lon": y,
                "demand": dem,
                "service_time": service * 60,
                "time_window": [ready * 60, due * 60],
                "depot": False,
            }
        )

    if waypoints:
        ids = [int(wp["id"]) for wp in waypoints]
        depot_id = 0 if 0 in ids else min(ids)
        for idx, wp in enumerate(waypoints):
            wp["depot"] = int(wp["id"]) == depot_id
            if wp["depot"]:
                depot_index = idx
                break

    vehicles = [
        {
            "id": f"veh-{i+1}",
            "start": depot_index,
            "end": depot_index,
            "capacity": [int(cap)],
            "skills": [],
            "time_window": None,
            "max_distance": None,
            "max_duration": None,
            "speed": None,
            "emissions_per_km": None,
        }
        for i in range(max(1, int(veh)))
    ]

    return {
        "edge_weight_type": "EUC_2D",
        "coordinate_spaces": {
            "solver": {"type": "euclidean", "fields": ["x", "y"]},
            "display": {"type": "wgs84", "fields": ["lon", "lat"]},
        },
        "waypoints": waypoints,
        "fleet": {"vehicles": vehicles},
        "depot_index": depot_index,
        "matrix": None,
        "meta": {
            "format": "solomon",
            "vehicle_count": int(veh),
            "capacity": int(cap),
        },
    }


# -------- Main entry for .vrp/.txt (CVRPLIB or Solomon) --------


def load_vrplib(file_path: str | Path, compute_matrix: bool = True) -> Dict[str, any]:
    p = Path(file_path)
    contents = p.read_text(encoding="utf-8", errors="ignore")

    if _is_solomon_text(contents):
        data = _parse_solomon_text(contents)
        if compute_matrix and data.get("waypoints"):
            coords_xy = [(wp["x"], wp["y"]) for wp in data["waypoints"]]
            distances = _build_distance_matrix_xy(coords_xy)
            durations = [
                [int(round(distances[i][j] * 60)) for j in range(len(distances))]
                for i in range(len(distances))
            ]
            data["matrix"] = {"distances": distances, "durations": durations}
        data["meta"]["source"] = str(p)
        return data

    lines = _tokenize_lines(contents)
    sections = _read_sections(lines)
    edge_type = _parse_edge_weight_type(lines) or "EUC_2D"

    vehicles_num, capacity = _parse_vehicle_header(lines)

    coord_lines = sections.get("NODE_COORD_SECTION", [])
    nodes = _parse_node_coord_section(coord_lines)
    if not nodes:
        raise ValueError("NODE_COORD_SECTION not found or empty.")

    dem_lines = sections.get("DEMAND_SECTION", [])
    demands = _parse_demand_section(dem_lines)

    tw_lines = sections.get("TIME_WINDOW_SECTION", [])
    st_lines = sections.get("SERVICE_TIME_SECTION", [])
    time_windows = _parse_time_window_section(tw_lines) if tw_lines else {}
    service_times = _parse_service_time_section(st_lines) if st_lines else {}

    depot_lines = sections.get("DEPOT_SECTION", [])
    depots = _parse_depot_section(depot_lines)
    depot_idx_1based = depots[0] if depots else 1
    depot_index = depot_idx_1based - 1

    waypoints: List[Dict] = []
    nodes_sorted = sorted(nodes, key=lambda t: t[0])
    for idx1, x, y in nodes_sorted:
        demand = int(demands.get(idx1, 0))
        tw = time_windows.get(idx1, None)
        service = int(service_times.get(idx1, 0))
        waypoints.append(
            {
                "id": str(idx1),
                # keep both spaces
                "x": float(x),
                "y": float(y),
                # legacy planar as lat/lon
                "lat": float(x),
                "lon": float(y),
                "demand": demand,
                "service_time": service,
                "time_window": list(tw) if tw else None,
                "depot": (idx1 - 1) == depot_index,
            }
        )

    vehicles: List[Dict] = [
        {
            "id": f"veh-{v_idx+1}",
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
        for v_idx in range(vehicles_num)
    ]

    matrix: Optional[Dict] = None
    if compute_matrix and waypoints:
        coords_xy = [(wp["x"], wp["y"]) for wp in waypoints]
        distances = _build_distance_matrix_xy(coords_xy)
        durations = [
            [distances[i][j] for j in range(len(distances))]
            for i in range(len(distances))
        ]
        matrix = {"distances": distances, "durations": durations}

    return {
        "edge_weight_type": edge_type,
        "coordinate_spaces": {
            "solver": (
                {"type": "euclidean", "fields": ["x", "y"]}
                if edge_type.startswith("EUC")
                else {"type": "wgs84", "fields": ["lon", "lat"]}
            ),
            "display": {"type": "wgs84", "fields": ["lon", "lat"]},
        },
        "waypoints": waypoints,
        "fleet": {"vehicles": vehicles},
        "depot_index": depot_index,
        "matrix": matrix,
        "meta": {
            "source": str(p),
            "format": "cvrplib",
            "vehicle_count": int(vehicles_num),
            "capacity": int(capacity),
        },
    }
