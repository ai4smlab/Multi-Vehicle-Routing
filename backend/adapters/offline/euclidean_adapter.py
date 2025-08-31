# backend/services/adapters/euclidean_adapter.py
from __future__ import annotations
from math import sqrt
from typing import Dict, Any, List, Optional


class EuclideanAdapter:
    """
    Offline adapter that computes pairwise Euclidean distances
    from solver-space coordinates (x,y). Units are "euclidean units".
    If you want meters, pass a scale factor.
    """

    def __init__(self, meters_per_unit: Optional[float] = None):
        self.meters_per_unit = meters_per_unit

    def matrix(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Request schema (flexible):
          - points: [{x,y}, ...] (preferred)
          - or waypoints: [{x,y}, ...]
          - or node_coord_section: [[id, x, y], ...]  (as parsed)
        """
        points = request.get("points") or request.get("waypoints") or []
        if not points and "node_coord_section" in request:
            points = [
                {"x": float(x), "y": float(y)}
                for _, x, y in request["node_coord_section"]
            ]

        coords: List[tuple] = []
        for p in points:
            x, y = p.get("x"), p.get("y")
            if x is None or y is None:
                raise ValueError("EuclideanAdapter requires x,y on each point")
            coords.append((float(x), float(y)))

        n = len(coords)
        dist = [[0.0] * n for _ in range(n)]
        for i in range(n):
            xi, yi = coords[i]
            for j in range(i + 1, n):
                xj, yj = coords[j]
                d = sqrt((xi - xj) ** 2 + (yi - yj) ** 2)
                if self.meters_per_unit:
                    d = d * self.meters_per_unit
                dist[i][j] = dist[j][i] = d

        return {
            "matrix": {
                "distances": dist,
                "durations": None,
                "coordinates": None,
                "units": "m" if self.meters_per_unit else "eu",
            }
        }
