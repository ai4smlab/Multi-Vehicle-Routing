# adapters/online/mapbox_matrix_adapter.py
from __future__ import annotations
from typing import List, Dict, Optional
import os
import httpx

from core.interfaces import DistanceMatrixAdapter
from models.distance_matrix import MatrixResult


class MapboxMatrixAdapter(DistanceMatrixAdapter):
    """
    DistanceMatrix adapter backed by Mapbox Directions Matrix API.
    - Supports rectangular O x D via `sources` / `destinations` query params.
    - Returns kilometers for distances; seconds for durations.
    """

    def __init__(self, api_key: Optional[str] = None, profile: str = "driving"):
        self.api_key = (
            api_key
            or os.getenv("MAPBOX_TOKEN")
            or os.getenv("MAPBOX_ACCESS_TOKEN")
            or "test-token"
        )
        self.profile = profile

    def _path(self, coords: List[Dict[str, float]]) -> str:
        return ";".join(f"{c['lon']},{c['lat']}" for c in coords)

    def get_matrix(
        self,
        origins: List[Dict[str, float]],
        destinations: List[Dict[str, float]],
        mode: str = "driving",
    ) -> MatrixResult:
        if not origins or not destinations:
            return MatrixResult(distances=[[0.0]], durations=[[0.0]])

        coords = (origins or []) + (destinations or [])
        n_o = len(origins)
        n_d = len(destinations)

        url = f"https://api.mapbox.com/directions-matrix/v1/mapbox/{self.profile}/{self._path(coords)}"

        sources = ";".join(str(i) for i in range(n_o))
        destinations_idx = ";".join(str(n_o + j) for j in range(n_d))

        # Ask Mapbox to compute just O x D to reduce payload
        params = {
            "annotations": "distance,duration",
            "sources": sources,
            "destinations": destinations_idx,
            "access_token": self.api_key,
            # units are meters/seconds by default
        }

        r = httpx.get(url, params=params, timeout=30.0)
        r.raise_for_status()
        data = r.json()

        # Mapbox returns meters for 'distances' (if requested)
        # Convert to km for consistency with other adapters in your app
        distances_m = data.get("distances")
        durations_s = data.get("durations")

        if distances_m is None and durations_s is None:
            # Fallback: empty
            return MatrixResult(
                distances=[[0.0] * n_d for _ in range(n_o)],
                durations=[[0.0] * n_d for _ in range(n_o)],
            )

        distances_km = None
        if distances_m is not None:
            distances_km = [[(x or 0.0) / 1000.0 for x in row] for row in distances_m]

        return MatrixResult(distances=distances_km, durations=durations_s)
