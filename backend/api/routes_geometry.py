# api/routes_geometry.py
from typing import Literal, Optional

import httpx
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

from api._coords import coerce_coords

router = APIRouter(prefix="/route", tags=["route"])


class GeomBody(BaseModel):
    coordinates: list  # accept anything; coerce in handler
    profile: Literal["driving", "walking", "cycling"] = "driving"
    provider: Literal["auto", "mapbox", "osrm"] = "auto"
    geometries: Literal["geojson", "polyline6"] = "geojson"
    tidy: bool = True
    osrm_url: Optional[str] = None  # fallback to env or public


@router.post("/geometry")
async def route_geometry(body: GeomBody = Body(...)):
    try:
        coords = coerce_coords(body.coordinates)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if body.provider in ("auto", "mapbox"):
        # proxy through our Mapbox match endpoint (centralizes auth/retries)
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(
                "http://localhost:8000/mapbox/match",
                json={
                    "profile": body.profile,
                    "coordinates": coords,  # dict shape: [{lon,lat}, ...]
                    "geometries": body.geometries,
                    "tidy": body.tidy,
                },
            )
        if r.status_code >= 400:
            raise HTTPException(r.status_code, r.text)
        j = r.json()
        geom = (j.get("matchings") or [{}])[0].get("geometry")
        if not geom:
            raise HTTPException(422, "No geometry in Mapbox response")
        return {"status": "success", "data": {"geometry": geom, "provider": "mapbox"}}

    # OSRM direct (geojson)
    import os

    base = (
        body.osrm_url or os.getenv("OSRM_URL") or "https://router.project-osrm.org"
    ).rstrip("/")
    path = ";".join(f"{c['lon']},{c['lat']}" for c in coords)
    url = f"{base}/route/v1/{body.profile}/{path}?overview=full&geometries=geojson"
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(url)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    j = r.json()
    geom = (j.get("routes") or [{}])[0].get("geometry")
    if not geom:
        raise HTTPException(422, "No geometry in OSRM response")
    return {"status": "success", "data": {"geometry": geom, "provider": "osrm"}}
