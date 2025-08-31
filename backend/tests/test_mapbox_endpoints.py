# backend/tests/test_mapbox_endpoints.py
import respx
import httpx
import traceback
from fastapi import HTTPException
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


@respx.mock
def test_mapbox_matrix_ok():
    try:
        respx.get("https://api.mapbox.com/directions-matrix/v1/mapbox/driving/*").mock(
            return_value=httpx.Response(
                200,
                json={
                    "distances": [[0, 1234], [1234, 0]],
                    "durations": [[0, 60], [60, 0]],
                },
            )
        )
        r = client.post(
            "/mapbox/matrix",
            json={
                "profile": "driving",
                "coordinates": [{"lon": 10, "lat": 20}, {"lon": 11, "lat": 21}],
                "annotations": ["distance", "duration"],
            },
        )
        assert r.status_code == 200
        j = r.json()
        assert j["distances"][0][1] == 1234
        assert j["durations"][1][0] == 60
    except Exception as e:
        print("MAPBOX ERR:", traceback.format_exc())
        raise HTTPException(500, f"Internal error: {e}") from e


@respx.mock
def test_mapbox_optimize_ok():
    try:
        respx.get("https://api.mapbox.com/optimized-trips/v1/mapbox/driving/*").mock(
            return_value=httpx.Response(
                200,
                json={
                    "code": "Ok",
                    "trips": [{"distance": 1000, "duration": 120}],
                    "waypoints": [],
                },
            )
        )
        r = client.post(
            "/mapbox/optimize",
            json={
                "profile": "driving",
                "coordinates": [{"lon": 10, "lat": 20}, {"lon": 11, "lat": 21}],
                "roundtrip": True,
                "source": "first",
                "destination": "last",
            },
        )
        assert r.status_code == 200
        assert r.json()["code"] == "Ok"
    except Exception as e:
        print("MAPBOX ERR:", traceback.format_exc())
        raise HTTPException(500, f"Internal error: {e}") from e


@respx.mock
def test_mapbox_match_ok():
    try:
        respx.get(
            "https://api.mapbox.com/mapbox/map-matching/v5/mapbox/driving/*"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "code": "Ok",
                    "matchings": [
                        {
                            "geometry": {
                                "type": "LineString",
                                "coordinates": [[10, 20], [11, 21]],
                            }
                        }
                    ],
                },
            )
        )
        r = client.post(
            "/mapbox/match",
            json={
                "profile": "driving",
                "coordinates": [{"lon": 10, "lat": 20}, {"lon": 11, "lat": 21}],
            },
        )
        assert r.status_code == 200
        assert r.json()["code"] == "Ok"
    except Exception as e:
        print("MAPBOX ERR:", traceback.format_exc())
        raise HTTPException(500, f"Internal error: {e}") from e


@respx.mock
def test_mapbox_geocode_ok():
    try:
        respx.get("https://api.mapbox.com/geocoding/v5/mapbox.places/*.json").mock(
            return_value=httpx.Response(
                200, json={"features": [{"place_name": "Test Place"}]}
            )
        )
        r = client.get("/mapbox/suggest", params={"q": "test", "limit": 3})
        assert r.status_code == 200
        assert r.json()["features"][0]["place_name"] == "Test Place"
    except Exception as e:
        print("MAPBOX ERR:", traceback.format_exc())
        raise HTTPException(500, f"Internal error: {e}") from e
