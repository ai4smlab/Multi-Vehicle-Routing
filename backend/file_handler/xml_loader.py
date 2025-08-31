# services/file_handler/xml_loader.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET
import math


def _text(el: Optional[ET.Element], default: Optional[str] = None) -> Optional[str]:
    return el.text.strip() if (el is not None and el.text is not None) else default


def _float_attr(el: ET.Element, *names: str) -> Optional[float]:
    for n in names:
        v = el.attrib.get(n)
        if v is not None:
            try:
                return float(v)
            except Exception:
                pass
    return None


def _int_attr(el: ET.Element, *names: str) -> Optional[int]:
    val = _float_attr(el, *names)
    return int(val) if val is not None else None


def _find_any(parent: ET.Element, *names: str) -> Optional[ET.Element]:
    for n in names:
        found = parent.find(n)
        if found is not None:
            return found
    # try case-insensitive search
    tags = {child.tag.lower(): child for child in parent}
    for n in names:
        if n.lower() in tags:
            return tags[n.lower()]
    return None


class VRPSetXMLLoader:
    """
    Loader for PUC-Rio 'vrp-set-xml 100' instances (robust to minor tag differences).
    Output is a dict compatible with your other loaders: waypoints, fleet, depot_index, matrix=None, meta.
    """

    def load_file(
        self, path: str | Path, compute_matrix: bool = True
    ) -> Dict[str, Any]:
        data = Path(path).read_bytes()
        return self.load_bytes(data, Path(path).name, compute_matrix=compute_matrix)

    def load_bytes(
        self,
        content: bytes,
        filename: str = "instance.xml",
        compute_matrix: bool = True,
    ) -> Dict[str, Any]:
        root = ET.fromstring(content)

        # Try to locate possible sections
        # Nodes/customers: look for 'nodes'/'vertices'/'customers'
        nodes_parent = _find_any(
            root, "nodes", "Vertices", "customers", "Customers", "vertexes"
        )
        if nodes_parent is None:
            # sometimes nested under <network> or <graph>
            net = _find_any(root, "network", "graph")
            if net is not None:
                nodes_parent = _find_any(
                    net, "nodes", "Vertices", "customers", "Customers", "vertexes"
                )
        if nodes_parent is None:
            raise ValueError("XML: could not find a nodes/customers/vertices section")

        # Fleet/capacity/vehicles
        fleet_parent = _find_any(root, "fleet", "vehicles", "vehicleInfo", "Resources")
        if fleet_parent is None:
            # sometimes under <data> or <instance>
            data = _find_any(root, "data", "instance")
            if data is not None:
                fleet_parent = _find_any(
                    data, "fleet", "vehicles", "vehicleInfo", "Resources"
                )

        # Default values
        vehicle_count = 1
        capacity = 10**9

        if fleet_parent is not None:
            # Look for typical attributes or child tags
            vc = None
            cap = None
            # attributes
            vc = vc or _int_attr(fleet_parent, "vehicles", "numVehicles", "fleetSize")
            cap = cap or _int_attr(fleet_parent, "capacity", "vehicleCapacity", "Q")
            # child tags
            vc = vc or (
                int(
                    _text(
                        _find_any(fleet_parent, "vehicles", "numVehicles", "fleetSize"),
                        "1",
                    )
                )
            )
            cap_txt = _text(
                _find_any(fleet_parent, "capacity", "vehicleCapacity", "Q"), None
            )
            if cap_txt is not None:
                try:
                    cap = int(float(cap_txt))
                except Exception:
                    pass
            if vc is not None:
                vehicle_count = vc
            if cap is not None:
                capacity = cap

        # Parse nodes/customers
        waypoints: List[Dict[str, Any]] = []
        depot_index = 0

        candidates = list(nodes_parent)
        if not candidates:
            raise ValueError("XML: nodes section appears empty")

        # Guess child tag names for nodes
        # common item tags: node, vertex, customer
        def _is_node_tag(t: str) -> bool:
            tl = t.lower()
            return tl in ("node", "vertex", "customer", "location")

        nodes = [el for el in candidates if _is_node_tag(el.tag)]
        if not nodes:
            nodes = candidates  # fallback: use all children

        # First pass to detect depot
        depot_flag_index: Optional[int] = None
        ids: List[int] = []

        for idx, node in enumerate(nodes):
            # id
            id_attr = _int_attr(node, "id", "number", "index")
            if id_attr is None:
                # try child <id>
                id_txt = _text(_find_any(node, "id", "ID"), None)
                id_attr = int(id_txt) if id_txt is not None else (idx + 1)
            ids.append(id_attr)

            # detect depot
            typ = node.attrib.get("type", "").lower()
            depot_tag = _find_any(node, "depot", "isDepot")
            is_depot = False
            if "depot" in typ:
                is_depot = True
            elif depot_tag is not None:
                txt = (_text(depot_tag, "") or "").lower()
                if txt in ("1", "true", "yes"):
                    is_depot = True
            elif node.attrib.get("isDepot", "").lower() in ("1", "true", "yes"):
                is_depot = True

            if is_depot:
                depot_flag_index = idx

        # If not found, assume smallest id is depot
        if depot_flag_index is None:
            if ids:
                depot_flag_index = ids.index(min(ids))
            else:
                depot_flag_index = 0

        # Second pass: build waypoint dicts
        for idx, node in enumerate(nodes):
            # coordinates (x,y) or (cx,cy) or children
            x = _float_attr(node, "x", "cx", "longitude", "lon", "long")
            y = _float_attr(node, "y", "cy", "latitude", "lat")
            if x is None or y is None:
                # child tags
                x_txt = _text(_find_any(node, "x", "cx", "longitude", "lon", "long"))
                y_txt = _text(_find_any(node, "y", "cy", "latitude", "lat"))
                if x is None and x_txt:
                    try:
                        x = float(x_txt)
                    except Exception:
                        x = 0.0
                if y is None and y_txt:
                    try:
                        y = float(y_txt)
                    except Exception:
                        y = 0.0
            if x is None:
                x = 0.0
            if y is None:
                y = 0.0

            dem = _int_attr(node, "demand", "dem", "q")
            if dem is None:
                dem_txt = _text(_find_any(node, "demand", "Dem"), "0")
                try:
                    dem = int(float(dem_txt))
                except Exception:
                    dem = 0

            # time windows
            tw_start = _int_attr(node, "ready", "twStart", "twA", "a", "open")
            tw_end = _int_attr(node, "due", "twEnd", "twB", "b", "close")
            if tw_start is None:
                tw_start_txt = _text(
                    _find_any(node, "ready", "twStart", "twA", "a", "open"), None
                )
                if tw_start_txt:
                    try:
                        tw_start = int(float(tw_start_txt))
                    except Exception:
                        tw_start = None
            if tw_end is None:
                tw_end_txt = _text(
                    _find_any(node, "due", "twEnd", "twB", "b", "close"), None
                )
                if tw_end_txt:
                    try:
                        tw_end = int(float(tw_end_txt))
                    except Exception:
                        tw_end = None

            service_time = _int_attr(node, "service", "serviceTime", "s", "duration")
            if service_time is None:
                st_txt = _text(
                    _find_any(node, "service", "serviceTime", "s", "duration"), "0"
                )
                try:
                    service_time = int(float(st_txt))
                except Exception:
                    service_time = 0

            waypoints.append(
                {
                    "id": str(ids[idx]),
                    # keep same convention as other loaders: planar x->lat, y->lon
                    "lat": float(x),
                    "lon": float(y),
                    "demand": int(dem),
                    "service_time": int(service_time or 0),
                    "time_window": (
                        [int(tw_start), int(tw_end)]
                        if (tw_start is not None and tw_end is not None)
                        else None
                    ),
                    "depot": (idx == depot_flag_index),
                }
            )

        depot_index = depot_flag_index or 0

        # Build a simple fleet (all vehicles identical)
        vehicles = []
        for i in range(max(1, int(vehicle_count))):
            vehicles.append(
                {
                    "id": f"veh-{i+1}",
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
            )

        matrix = None
        if compute_matrix:
            coords = [(wp["lat"], wp["lon"]) for wp in waypoints]
            n = len(coords)
            dist = [[0.0] * n for _ in range(n)]
            for i in range(n):
                for j in range(i + 1, n):
                    d = math.hypot(
                        coords[i][0] - coords[j][0], coords[i][1] - coords[j][1]
                    )
                    dist[i][j] = dist[j][i] = d
            matrix = {"distances": dist, "durations": [row[:] for row in dist]}

        return {
            "waypoints": waypoints,
            "fleet": {"vehicles": vehicles},
            "depot_index": depot_index,
            "matrix": matrix,  # now present when requested
            "meta": {
                "source": filename,
                "format": "vrp-set-xml",
                "vehicle_count": int(vehicle_count),
                "capacity": int(capacity),
            },
        }
