import math
from typing import List
from core.interfaces import DistanceMatrixAdapter
from core.exceptions import DistanceMatrixRequestError
from models.distance_matrix import MatrixRequest, MatrixResult


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0  # km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    )
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))  # km


class HaversineAdapter(DistanceMatrixAdapter):
    """
    Offline adapter. Returns distances in **km**; durations/emissions None.
    """

    async def get_matrix(self, request: MatrixRequest) -> MatrixResult:
        if not request.origins:
            raise DistanceMatrixRequestError("Haversine: 'origins' is required.")
        # If destinations omitted, treat as square matrix (origins→origins)
        destinations = request.destinations or request.origins

        distances: List[List[float]] = []
        for o in request.origins:
            row = []
            for d in destinations:
                row.append(_haversine_km(o.lat, o.lon, d.lat, d.lon))
            distances.append(row)

        return MatrixResult(distances=distances, durations=None)
