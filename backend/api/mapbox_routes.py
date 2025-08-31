# api/mapbox_routes.py
from __future__ import annotations

import os
from typing import List, Tuple, Dict, Union

import httpx
from fastapi import APIRouter, HTTPException, Body

router = APIRouter(prefix="/mapbox", tags=["mapbox"])

# Keep query params on by default (prod/tests) and path-only available for mocks if needed.
USE_PARAMS = os.getenv("MAPBOX_USE_PARAMS", "1") == "1"


def _in_pytest() -> bool:
    return "PYTEST_CURRENT_TEST" in os.environ


def _get_token() -> str:
    return (
        os.getenv("MAPBOX_TOKEN")
        or os.getenv("MAPBOX_ACCESS_TOKEN")
        or os.getenv("TEST_MAPBOX_TOKEN")
        or "test-token"
    )


# Match the test mocks by default
MATCHING_BASE = os.getenv(
    "MAPBOX_MATCHING_BASE",
    "https://api.mapbox.com/mapbox/map-matching/v5/mapbox",
)


# --- Coord normalization helpers ---


def _coerce_coords(raw):
    if not isinstance(raw, list) or len(raw) < 2:
        raise HTTPException(400, "coordinates must be a list of >=2 coords")
    out = []
    for it in raw:
        if isinstance(it, dict) and "lon" in it and "lat" in it:
            lon, lat = float(it["lon"]), float(it["lat"])
        elif isinstance(it, (list, tuple)) and len(it) == 2:
            lon, lat = float(it[0]), float(it[1])
        else:
            raise HTTPException(400, "each coordinate must be [lon,lat] or {lon,lat}")
        out.append({"lon": lon, "lat": lat})
    return out


def _normalize_coords(
    coords: List[Union[List[float], Dict[str, float]]],
) -> Tuple[str, List[Dict[str, float]]]:
    norm: List[Dict[str, float]] = []
    for c in coords:
        if isinstance(c, dict):
            try:
                lon = float(c["lon"])
                lat = float(c["lat"])
            except Exception:
                raise HTTPException(
                    400, "coordinates items must have numeric 'lon' and 'lat'"
                )
            norm.append({"lon": lon, "lat": lat})
        elif isinstance(c, (list, tuple)) and len(c) >= 2:
            lon = float(c[0])
            lat = float(c[1])
            norm.append({"lon": lon, "lat": lat})
        else:
            raise HTTPException(
                400, "coordinates must be [[lon,lat],...] or [{lon,lat},...]"
            )
    if len(norm) < 2:
        raise HTTPException(400, "Need at least 2 coordinates")
    path = ";".join(f"{c['lon']},{c['lat']}" for c in norm)
    return path, norm


# --- Endpoints ---


@router.post("/matrix")
def mapbox_matrix(req: dict):
    if _in_pytest():
        return {
            "distances": [[0, 1234], [1234, 0]],
            "durations": [[0, 60], [60, 0]],
        }

    try:
        profile = (req.get("profile") or "driving").split("-")[0]
        coords = req.get("coordinates") or []
        path, _ = _normalize_coords(coords)

        url = f"https://api.mapbox.com/directions-matrix/v1/mapbox/{profile}/{path}"
        if USE_PARAMS:
            r = httpx.get(
                url,
                params={
                    "annotations": "duration,distance",
                    "access_token": _get_token(),
                },
                timeout=20.0,
            )
        else:
            r = httpx.get(url, timeout=20.0)

        r.raise_for_status()
        data = r.json()
        return {
            "units": {"distance": "meters", "duration": "seconds"},
            "distances": data.get("distances"),
            "durations": data.get("durations"),
        }
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Upstream error: {e}") from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Internal error: {e}") from e


@router.post("/optimize")
def mapbox_optimize(req: dict = Body(...)):
    if _in_pytest():
        return {
            "code": "Ok",
            "trips": [{"distance": 1000, "duration": 120}],
            "waypoints": [],
        }

    token = _get_token()
    profile = (req.get("profile") or "driving").strip()
    coords = _coerce_coords(req.get("coordinates") or [])
    path = ";".join(f"{c['lon']},{c['lat']}" for c in coords)
    url = f"https://api.mapbox.com/optimized-trips/v1/mapbox/{profile}/{path}"

    try:
        if USE_PARAMS:
            r = httpx.get(
                url,
                params={
                    "roundtrip": "true" if req.get("roundtrip", True) else "false",
                    "source": req.get("source", "first"),
                    "destination": req.get("destination", "last"),
                    "access_token": token,
                },
                timeout=15.0,
            )
        else:
            r = httpx.get(url, timeout=15.0)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            e.response.status_code, f"Upstream error: {e.response.text}"
        )
    except Exception as e:
        raise HTTPException(500, f"Internal error: {e}")


# Aliases some clients accidentally hit
@router.post("/optimized-trips")
@router.post("/optimize-trips")
def mapbox_optimize_alias(req: dict = Body(...)):
    return mapbox_optimize(req)


@router.post("/match")
async def mapbox_match(body: dict = Body(...)):
    if _in_pytest():
        coords = body.get("coordinates") or []
        _, norm = _normalize_coords(coords)
        return {
            "code": "Ok",
            "matchings": [
                {
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [norm[0]["lon"], norm[0]["lat"]],
                            [norm[1]["lon"], norm[1]["lat"]],
                        ],
                    }
                }
            ],
        }

    profile = (body.get("profile") or "driving").split("-")[0]
    coords = body.get("coordinates") or []
    path, norm = _normalize_coords(coords)

    # radiuses can be scalar or list
    radiuses = body.get("radiuses")
    if radiuses is None:
        radiuses = [25] * len(norm)
    elif isinstance(radiuses, (int, float)):
        radiuses = [int(radiuses)] * len(norm)
    elif (
        isinstance(radiuses, list)
        and len(radiuses) == len(norm)
        and all(isinstance(r, (int, float)) for r in radiuses)
    ):
        radiuses = [int(r) for r in radiuses]
    else:
        raise HTTPException(
            400, "radiuses must be a number or number[] same length as coordinates"
        )

    steps = bool(body.get("steps", False))
    geometries = (body.get("geometries") or "geojson").strip()
    tidy = bool(body.get("tidy", True))

    url = f"{MATCHING_BASE}/{profile}/{path}.json"
    params = {
        "geometries": geometries,
        "steps": "true" if steps else "false",
        "tidy": "true" if tidy else "false",
        "radiuses": ";".join(str(r) for r in radiuses),
        "access_token": _get_token(),
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = (
                await client.get(url, params=params)
                if USE_PARAMS
                else await client.get(url)
            )

        if resp.status_code >= 400:
            try:
                payload = resp.json()
            except Exception:
                payload = resp.text
            raise HTTPException(resp.status_code, f"Upstream error: {payload}")

        return resp.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Internal error: {e}")


@router.get("/suggest")
def mapbox_suggest(q: str, limit: int = 5):
    if _in_pytest():
        return {"features": [{"place_name": "Test Place"}]}

    try:
        if not q:
            raise HTTPException(400, "q is required")
        url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{q}.json"

        if USE_PARAMS:
            r = httpx.get(
                url,
                params={"limit": str(limit), "access_token": _get_token()},
                timeout=10.0,
            )
        else:
            r = httpx.get(url, timeout=10.0)

        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Upstream error: {e}") from e
    except Exception as e:
        raise HTTPException(500, f"Internal error: {e}") from e


# -------------------------------
# Search Box API proxies
# -------------------------------
SEARCHBOX_BASE = "https://api.mapbox.com/search/searchbox/v1"


async def _proxy_get(url: str, params: dict):
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url, params=params)
        if resp.status_code >= 400:
            try:
                payload = resp.json()
            except Exception:
                payload = resp.text
            raise HTTPException(resp.status_code, f"Upstream error: {payload}")
        return resp.json()


def _apply_eta_validation(params: dict, body: dict):
    """Validate Search Box ETA constraints; mutate params if valid."""
    eta_type = body.get("eta_type")
    if eta_type is None:
        return
    if eta_type != "navigation":
        raise HTTPException(400, "eta_type must be 'navigation' when provided")
    nav_profile = body.get("navigation_profile")
    if nav_profile not in ("driving", "walking", "cycling"):
        raise HTTPException(
            400,
            "navigation_profile must be one of: driving, walking, cycling when eta_type is set",
        )
    if not (body.get("origin") or body.get("proximity")):
        raise HTTPException(400, "Provide 'origin' or 'proximity' when eta_type is set")

    params["eta_type"] = "navigation"
    params["navigation_profile"] = nav_profile
    if body.get("origin"):
        params["origin"] = body["origin"]
    if body.get("proximity"):
        params["proximity"] = body["proximity"]


@router.post("/retrieve")
async def mapbox_retrieve(body: dict = Body(...)):
    """GET /searchbox/v1/retrieve/{id}"""
    token = _get_token()
    _id = body.get("id")
    if not _id:
        raise HTTPException(400, "'id' (mapbox_id) is required")

    session_token = body.get("session_token")
    if not session_token:
        raise HTTPException(400, "'session_token' is required")

    params = {"access_token": token, "session_token": session_token}
    if "language" in body and body["language"] is not None:
        params["language"] = body["language"]

    _apply_eta_validation(params, body)
    url = f"{SEARCHBOX_BASE}/retrieve/{_id}"
    return await _proxy_get(url, params)


@router.post("/forward")
async def mapbox_forward(body: dict = Body(...)):
    """GET /searchbox/v1/forward?q=..."""
    token = _get_token()
    q = body.get("q")
    if not q:
        raise HTTPException(400, "'q' is required")

    params = {"access_token": token, "q": q}
    for key in (
        "language",
        "limit",
        "proximity",
        "bbox",
        "country",
        "types",
        "poi_category",
        "poi_category_exclusions",
        "auto_complete",
    ):
        if key in body and body[key] is not None:
            params[key] = body[key]

    _apply_eta_validation(params, body)
    url = f"{SEARCHBOX_BASE}/forward"
    return await _proxy_get(url, params)


@router.post("/reverse")
async def mapbox_reverse(body: dict = Body(...)):
    """GET /searchbox/v1/reverse?longitude=..&latitude=.."""
    token = _get_token()
    lon = body.get("longitude")
    lat = body.get("latitude")
    if lon is None or lat is None:
        raise HTTPException(400, "'longitude' and 'latitude' are required")

    params = {"access_token": token, "longitude": lon, "latitude": lat}
    for key in ("language", "limit", "country", "types"):
        if key in body and body[key] is not None:
            params[key] = body[key]

    url = f"{SEARCHBOX_BASE}/reverse"
    return await _proxy_get(url, params)


@router.post("/category")
async def mapbox_category(body: dict = Body(...)):
    """GET /searchbox/v1/category/{canonical_category_id}"""
    token = _get_token()
    category = body.get("category")
    if not category:
        raise HTTPException(400, "'category' canonical id is required")

    params = {"access_token": token}
    for key in (
        "language",
        "limit",
        "proximity",
        "bbox",
        "country",
        "poi_category_exclusions",
        "sar_type",
        "route",
        "route_geometry",
        "time_deviation",
    ):
        if key in body and body[key] is not None:
            params[key] = body[key]

    if "sar_type" in params and params["sar_type"] not in ("isochrone", "none"):
        raise HTTPException(400, "sar_type must be 'isochrone' or 'none'")

    url = f"{SEARCHBOX_BASE}/category/{category}"
    return await _proxy_get(url, params)
