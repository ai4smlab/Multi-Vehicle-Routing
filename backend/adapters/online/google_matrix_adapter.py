import httpx
from core.interfaces import DistanceMatrixAdapter
from models.distance_matrix import MatrixRequest, MatrixResult
from core.exceptions import DistanceMatrixRequestError

GOOGLE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"


class GoogleMatrixAdapter(DistanceMatrixAdapter):
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def get_matrix(self, request: MatrixRequest) -> MatrixResult:
        try:
            if not request.origins or not request.destinations:
                raise DistanceMatrixRequestError(
                    "Google Matrix requires both 'origins' and 'destinations'."
                )

            # Extract optional mode from parameters
            mode = request.parameters.get("mode", "driving")

            # Format origins and destinations as required by Google API
            origins = "|".join(f"{coord.lat},{coord.lon}" for coord in request.origins)
            destinations = "|".join(
                f"{coord.lat},{coord.lon}" for coord in request.destinations
            )

            # Compose request parameters
            params = {
                "origins": origins,
                "destinations": destinations,
                "mode": mode,
                "units": "metric",
                "key": self.api_key,
            }

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(GOOGLE_MATRIX_URL, params=params)
                response.raise_for_status()
                data = response.json()

            # Error handling based on API status
            if data.get("status") != "OK":
                raise DistanceMatrixRequestError(
                    f"Google API error: {data.get('error_message', 'Unknown error')}"
                )

            return MatrixResult.from_google(data)

        except Exception as e:
            raise DistanceMatrixRequestError(f"Failed to fetch Google matrix: {e}")
