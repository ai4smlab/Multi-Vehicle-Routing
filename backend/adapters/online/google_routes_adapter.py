import os
import httpx
import re
from typing import List, Tuple, Union
from core.interfaces import DistanceMatrixAdapter
from core.exceptions import DistanceMatrixRequestError
from models.distance_matrix import MatrixRequest, MatrixResult

CoordinateType = Union[Tuple[float, float], List[float], object]


class GoogleRoutesAdapter(DistanceMatrixAdapter):
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GOOGLE_ROUTES_API_KEY")
        if not self.api_key:
            raise DistanceMatrixRequestError("Google Routes API key not provided.")

    @staticmethod
    def _to_latlon(coord: CoordinateType) -> Tuple[float, float]:
        if hasattr(coord, "lat") and hasattr(coord, "lng"):
            return (float(coord.lat), float(coord.lng))
        if hasattr(coord, "lat") and hasattr(
            coord, "lon"
        ):  # Support lon instead of lng
            return (float(coord.lat), float(coord.lon))
        if hasattr(coord, "latitude") and hasattr(coord, "longitude"):
            return (float(coord.latitude), float(coord.longitude))
        if isinstance(coord, (list, tuple)) and len(coord) == 2:
            return (float(coord[0]), float(coord[1]))
        if (
            isinstance(coord, dict)
            and "lat" in coord
            and ("lng" in coord or "lon" in coord)
        ):
            return (float(coord["lat"]), float(coord.get("lng", coord.get("lon"))))
        raise ValueError(f"Invalid coordinate format: {coord}")

    @staticmethod
    def _parse_duration(duration_str: str) -> float:
        if duration_str.endswith("s") and duration_str[:-1].isdigit():
            return float(duration_str[:-1])
        match = re.match(r"PT(?:(\d+)M)?(?:(\d+)S)?", duration_str)
        if match:
            minutes = int(match.group(1) or 0)
            seconds = int(match.group(2) or 0)
            return minutes * 60 + seconds
        return 0.0

    async def get_matrix(self, request: MatrixRequest) -> MatrixResult:
        origins_list = [self._to_latlon(o) for o in request.origins]
        destinations_list = [
            self._to_latlon(d) for d in (request.destinations or request.origins)
        ]

        mode_map = {
            "driving": "DRIVE",
            "walking": "WALK",
            "bicycling": "BICYCLE",
        }
        travel_mode = mode_map.get(request.mode.lower(), "DRIVE")

        request_body = {
            "origins": [
                {"location": {"latLng": {"latitude": lat, "longitude": lon}}}
                for lat, lon in origins_list
            ],
            "destinations": [
                {"location": {"latLng": {"latitude": lat, "longitude": lon}}}
                for lat, lon in destinations_list
            ],
            "travelMode": travel_mode,
        }

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "originIndex,destinationIndex,distanceMeters,duration",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix",
                json=request_body,
                headers=headers,
            )

        if response.status_code != 200:
            raise DistanceMatrixRequestError(
                f"Google Routes API error: {response.text}"
            )

        rows = response.json()
        n = len(origins_list)
        m = len(destinations_list)
        distances = [[0.0 for _ in range(m)] for _ in range(n)]
        durations = [[0.0 for _ in range(m)] for _ in range(n)]

        for element in rows:
            oi = element["originIndex"]
            di = element["destinationIndex"]
            if "distanceMeters" in element:
                distances[oi][di] = element["distanceMeters"] / 1000.0
            if "duration" in element:
                durations[oi][di] = self._parse_duration(element["duration"])

        return MatrixResult(
            distances=distances if "distance" in request.metrics else None,
            durations=durations if "duration" in request.metrics else None,
        )
