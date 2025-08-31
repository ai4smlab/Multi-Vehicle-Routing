# adapters/offline/osm_graph_adapter.py
from __future__ import annotations
from typing import List, Dict, Tuple, Optional, Callable
from functools import lru_cache
import re

import osmnx as ox
import networkx as nx

from core.interfaces import DistanceMatrixAdapter
from models.distance_matrix import MatrixResult

ox.settings.log_console = False
ox.settings.use_cache = True


def _center(coords: List[Dict[str, float]]) -> Tuple[float, float]:
    lat = sum(c["lat"] for c in coords) / len(coords)
    lon = sum(c["lon"] for c in coords) / len(coords)
    return (lat, lon)


def _ensure_lengths(G):
    """Ensure every edge has 'length' in meters, across OSMnx versions."""
    try:
        from osmnx import distance as ox_distance  # new location

        G = ox_distance.add_edge_lengths(G)
    except Exception:
        if hasattr(ox, "add_edge_lengths"):  # legacy fallback
            G = ox.add_edge_lengths(G)
    return G


def _parse_speed_kph(val) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, list) and val:
        return _parse_speed_kph(val[0])
    if isinstance(val, str):
        m = re.search(r"(\d+(\.\d+)?)", val)
        if m:
            v = float(m.group(1))
            if "mph" in val.lower():
                v *= 1.60934
            return v
    return None


def _impute_travel_times(G, default_kph: float = 50.0):
    """Create 'travel_time' (seconds) from 'length' and 'maxspeed' (km/h)."""
    defaults = {
        "motorway": 100.0,
        "trunk": 90.0,
        "primary": 80.0,
        "secondary": 60.0,
        "tertiary": 50.0,
        "residential": 30.0,
        "living_street": 20.0,
        "service": 20.0,
    }
    for _, _, _, data in G.edges(keys=True, data=True):
        length_m = float(data.get("length", 0.0))
        speed_kph = _parse_speed_kph(data.get("maxspeed"))
        if speed_kph is None:
            hwy = data.get("highway")
            if isinstance(hwy, list) and hwy:
                hwy = hwy[0]
            speed_kph = defaults.get(hwy, default_kph)
        data["travel_time"] = (length_m * 3.6) / float(speed_kph or default_kph)
    return G


@lru_cache(maxsize=64)
def _build_graph(lat: float, lon: float, dist_buffer: int, network_type: str = "drive"):
    G = ox.graph_from_point(
        (lat, lon), dist=dist_buffer, network_type=network_type, simplify=True
    )
    G = _ensure_lengths(G)
    G = _impute_travel_times(G)
    return G


def _nearest_nodes(G, coords: List[Dict[str, float]]) -> List[int]:
    xs = [c["lon"] for c in coords]
    ys = [c["lat"] for c in coords]
    nodes = ox.distance.nearest_nodes(G, xs, ys)
    return list(nodes) if hasattr(nodes, "__iter__") else [nodes]


# Reasonable “unreachable” caps to avoid solver overflows/quirks
# Distances are returned in km, durations in seconds.
_INF_DISTANCE_KM = 1e6  # ~1,000,000 km
_INF_DURATION_S = 1e7  # ~115 days


class OsmGraphAdapter(DistanceMatrixAdapter):
    """Local OSM-based routing using OSMnx + NetworkX.

    Now supports both:
      - square matrices: build_matrix(coords) / matrix(coords) / distance_matrix(coords)
      - rectangular matrices: build(origins, destinations), get_matrix(origins, destinations)
    """

    def __init__(
        self,
        buffer_m: int = 3000,
        network_type: str = "drive",
        graph_factory: Optional[
            Callable[[float, float, int, str], nx.MultiDiGraph]
        ] = None,
        node_locator: Optional[
            Callable[[nx.MultiDiGraph, List[Dict[str, float]]], List[int]]
        ] = None,
    ):
        self.buffer_m = int(buffer_m)
        self.network_type = network_type
        # DI hooks for tests
        self._graph_factory = graph_factory
        self._node_locator = node_locator

    def _make_graph(self, lat: float, lon: float, network_type: Optional[str] = None):
        nt = network_type or self.network_type
        if self._graph_factory:
            return self._graph_factory(lat, lon, self.buffer_m, nt)
        return _build_graph(lat, lon, self.buffer_m, nt)

    def _locate_nodes(self, G, coords):
        if self._node_locator:
            return self._node_locator(G, coords)
        return _nearest_nodes(G, coords)

    # ── Single-list convenience (square N×N) ───────────────────────────────────
    def build_matrix(
        self, coords: List[Dict[str, float]], mode: str = "driving"
    ) -> MatrixResult:
        return self.build(coords, coords, mode)

    # Common aliases other parts of the code may look for
    def matrix(
        self, coords: List[Dict[str, float]], mode: str = "driving"
    ) -> MatrixResult:
        return self.build_matrix(coords, mode)

    def distance_matrix(
        self, coords: List[Dict[str, float]], mode: str = "driving"
    ) -> MatrixResult:
        return self.build_matrix(coords, mode)

    def fetch_matrix(
        self, coords: List[Dict[str, float]], mode: str = "driving"
    ) -> MatrixResult:
        return self.build_matrix(coords, mode)

    # ── Two-list rectangular matrix (origins × destinations) ───────────────────
    def get_matrix(
        self,
        origins: List[Dict[str, float]],
        destinations: Optional[List[Dict[str, float]]] = None,
        mode: str = "driving",
    ) -> MatrixResult:
        # Backward compat: if destinations omitted, assume square matrix
        if destinations is None:
            destinations = origins
        return self.build(origins, destinations, mode)

    def build(
        self,
        origins: List[Dict[str, float]],
        destinations: List[Dict[str, float]],
        mode: str = "driving",
    ) -> MatrixResult:
        origins = origins or []
        destinations = destinations or []
        coords = origins + destinations
        if not coords:
            return MatrixResult(distances=[[0.0]], durations=[[0.0]])

        lat, lon = _center(coords)

        # Allow caller to override mode per call (optional)
        nt = self.network_type
        m = mode.lower().strip()
        if m in ("walk", "walking"):
            nt = "walk"
        elif m in ("bike", "cycling", "bicycle"):
            nt = "bike"
        elif m in ("drive", "driving", "car"):
            nt = "drive"

        G = self._make_graph(lat, lon, network_type=nt)

        o_nodes = self._locate_nodes(G, origins)
        d_nodes = self._locate_nodes(G, destinations)

        D_km = [[0.0] * len(d_nodes) for _ in range(len(o_nodes))]
        T_s = [[0.0] * len(d_nodes) for _ in range(len(o_nodes))]

        for i, u in enumerate(o_nodes):
            # Dijkstra once per origin for distance and time
            dlen = nx.single_source_dijkstra_path_length(G, u, weight="length")
            tlen = nx.single_source_dijkstra_path_length(G, u, weight="travel_time")
            for j, v in enumerate(d_nodes):
                dm = float(dlen.get(v, float("inf")))  # meters
                tm = float(tlen.get(v, float("inf")))  # seconds
                if dm == float("inf") or tm == float("inf"):
                    # Clamp unreachable pairs to large but finite penalties
                    D_km[i][j] = _INF_DISTANCE_KM
                    T_s[i][j] = _INF_DURATION_S
                else:
                    D_km[i][j] = dm / 1000.0
                    T_s[i][j] = tm

        return MatrixResult(distances=D_km, durations=T_s)
