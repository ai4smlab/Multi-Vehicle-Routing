import httpx
from typing import Any

from core.interfaces import DistanceMatrixAdapter
from core.exceptions import DistanceMatrixRequestError
from models.distance_matrix import MatrixRequest, MatrixResult


def _as_lonlat(coord: Any) -> list[float]:
    """
    Return [lon, lat] from a coordinate-like object.
    Supports objects with .lat/.lon or dicts with those keys.
    """
    if hasattr(coord, "lat") and hasattr(coord, "lon"):
        return [float(coord.lon), float(coord.lat)]
    # allow dict-like for extra robustness
    c = coord  # type: ignore
    return [float(c["lon"]), float(c["lat"])]


def _as_key(coord: Any) -> tuple[float, float]:
    """Key used for deduplication: (lat, lon)."""
    if hasattr(coord, "lat") and hasattr(coord, "lon"):
        return (float(coord.lat), float(coord.lon))
    c = coord  # type: ignore
    return (float(c["lat"]), float(c["lon"]))


def _normalize_distances_in_place(data: dict, units: str | None) -> None:
    """
    Ensure distances are integer meters for downstream solvers.
    - If ORS answered in km/mi, convert to meters.
    - If already in meters, round to ints.
    - If units is unknown and values look tiny (<20 on off-diagonal), treat as km.
    """
    distances = data.get("distances")
    if not distances:
        return

    n = len(distances)
    # gather off-diagonal positives to estimate scale
    offdiag: list[float] = []
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            v = distances[i][j]
            if v is not None:
                offdiag.append(float(v))

    if not offdiag:
        # nothing to do
        return

    factor = 1.0
    u = (units or "").lower()
    if u == "km":
        factor = 1000.0
    elif u in ("mi", "mile", "miles"):
        factor = 1609.344
    elif u in ("m", "", None):
        # Likely already meters; keep factor=1
        # But if values are very small, infer km (common in loose mocks)
        max_v = max(offdiag)
        if max_v > 0 and max_v < 20:
            factor = 1000.0
    else:
        # Unknown units; try auto-detect like above
        max_v = max(offdiag)
        if max_v > 0 and max_v < 20:
            factor = 1000.0

    # Convert + round to integer meters
    for i in range(n):
        row = distances[i]
        for j in range(n):
            if i == j:
                row[j] = 0
                continue
            v = row[j]
            if v is None:
                row[j] = None
            else:
                row[j] = int(round(float(v) * factor))


class ORSDistanceMatrixAdapter(DistanceMatrixAdapter):
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def get_matrix(self, request: MatrixRequest) -> MatrixResult:
        try:
            # === 1) Extract & validate input ===
            origins = request.origins
            destinations = request.destinations
            if not origins or not destinations:
                raise DistanceMatrixRequestError(
                    "ORS requires both 'origins' and 'destinations'."
                )

            parameters = request.parameters or {}
            mode_map = {
                "driving": "driving-car",
                "cycling": "cycling-regular",
                "walking": "foot-walking",
            }
            profile = mode_map.get((request.mode or "driving").lower(), "driving-car")
            metrics: list[str] = parameters.get("metrics", ["distance", "duration"])
            units: str = parameters.get("units", "m")  # ORS supports 'm', 'km', 'mi'

            # === 2) Deduplicate coordinates & build index maps ===
            all_coords = list(origins) + list(destinations)
            unique_coords: list[list[float]] = []
            coord_index_map: dict[tuple[float, float], int] = {}

            for coord in all_coords:
                key = _as_key(coord)
                if key not in coord_index_map:
                    coord_index_map[key] = len(unique_coords)
                    unique_coords.append(_as_lonlat(coord))  # ORS expects [lon, lat]

            source_indices = [coord_index_map[_as_key(wp)] for wp in origins]
            dest_indices = [coord_index_map[_as_key(wp)] for wp in destinations]

            # === 3) Build request ===
            payload = {
                "locations": unique_coords,
                "sources": source_indices,
                "destinations": dest_indices,
                "metrics": metrics,
                "units": units,
            }

            headers = {
                "Authorization": self.api_key,
                "Content-Type": "application/json",
            }

            url = f"https://api.openrouteservice.org/v2/matrix/{profile}"

            # === 4) Send request ===
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()

            # === 5) Normalize distances (int meters) & return ===
            _normalize_distances_in_place(data, units)
            return MatrixResult.from_ors(data)

        except httpx.HTTPStatusError as e:
            # include ORS body text for easier debugging in tests
            raise DistanceMatrixRequestError(f"ORS HTTP error: {e.response.text}")
        except Exception as e:
            raise DistanceMatrixRequestError(f"OpenRouteService error: {e}")
