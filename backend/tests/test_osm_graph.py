# backend/tests/test_osm_graph.py
import networkx as nx
import pytest
from adapters.online.osm_graph_adapter import OsmGraphAdapter


def _toy_graph_factory(lat, lon, buffer_m, network_type):
    # Simple 3-node directed graph
    G = nx.DiGraph()
    # OSMnx-style positions: x=lon, y=lat
    G.add_node(1, x=0.0, y=0.0)
    G.add_node(2, x=1.0, y=0.0)
    G.add_node(3, x=1.0, y=1.0)
    # Edges with meters & seconds
    G.add_edge(1, 2, length=100.0, travel_time=10.0)
    G.add_edge(2, 3, length=150.0, travel_time=15.0)
    G.add_edge(1, 3, length=400.0, travel_time=40.0)
    return G


def _node_locator(G, coords):
    """
    Map coords to the nearest *existing* node by Euclidean distance in (lon,lat)
    space using the node attributes (x=lon, y=lat). That way, origins and
    destinations can resolve to different nodes even when passed separately.
    """
    out = []
    for c in coords:
        cx, cy = float(c["lon"]), float(c["lat"])
        best = None
        best_d2 = float("inf")
        for nid, data in G.nodes(data=True):
            dx = data["x"] - cx
            dy = data["y"] - cy
            d2 = dx * dx + dy * dy
            if d2 < best_d2:
                best_d2 = d2
                best = nid
        out.append(best)
    return out


def test_adapter_offline_di():
    adapter = OsmGraphAdapter(
        buffer_m=1500,
        graph_factory=_toy_graph_factory,
        node_locator=_node_locator,
    )

    # Origin near node 1, destination near node 3
    origins = [{"lat": 0.0, "lon": 0.0}]
    destinations = [{"lat": 1.0, "lon": 1.0}]

    m = adapter.get_matrix(origins, destinations)

    # Distances are returned in km; shortest 1->3 is 1->2->3: (100 + 150) m = 0.25 km
    assert m.distances[0][0] == pytest.approx(0.25)
    # Durations are seconds: 10 + 15 = 25
    assert m.durations[0][0] == pytest.approx(25.0)
