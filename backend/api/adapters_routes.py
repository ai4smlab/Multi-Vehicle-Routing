# api/adapters_routes.py
import os
import asyncio
import inspect
from typing import List, Optional, Dict, Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from adapters.adapter_factory import create_adapter
from adapters.online.openrouteservice_adapter import ORSDistanceMatrixAdapter
from core.exceptions import DistanceMatrixRequestError
from core.cache import ors_matrix_cache
from models.distance_matrix import MatrixRequest, MatrixResult

router = APIRouter()


# ───────────────────────── types ─────────────────────────


class Coordinate(BaseModel):
    lat: float
    lon: float


class ORSMatrixBody(BaseModel):
    """
    Minimal, frontend-friendly body:
      - coordinates may be {lat,lon} or [lon,lat]
      - destinations optional; if omitted, origins are mirrored
    """

    origins: List[Coordinate]
    destinations: Optional[List[Coordinate]] = None
    mode: Literal["driving", "cycling", "walking"] = "driving"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {"metrics": ["distance", "duration"], "units": "m"}
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_shapes(cls, v: Dict[str, Any]):
        def to_coord(c):
            if isinstance(c, dict):
                return {"lat": float(c["lat"]), "lon": float(c["lon"])}
            if isinstance(c, (list, tuple)) and len(c) >= 2:
                # UI sometimes sends [lon,lat] arrays
                return {"lat": float(c[1]), "lon": float(c[0])}
            raise ValueError("Coordinate must be {lat,lon} or [lon,lat]")

        if "origins" in v:
            v["origins"] = [to_coord(c) for c in v["origins"]]
        if v.get("destinations") is not None:
            v["destinations"] = [to_coord(c) for c in v["destinations"]]
        return v


# ───────────────────────── legacy / generic entrypoint ─────────────────────────
@router.post(
    "/distance-matrix", summary="Compute a distance/duration matrix via adapter"
)
async def get_distance_matrix(req: MatrixRequest):
    """
    Back-compat route that accepts a MatrixRequest with `adapter` set.
    It bridges to adapters that expect either (request) or (origins, destinations, ...).
    """
    try:
        adapter = create_adapter(req.adapter)

        def _as_plain_coords(items):
            return [
                (it if isinstance(it, dict) else {"lat": it.lat, "lon": it.lon})
                for it in (items or [])
            ]

        gm = getattr(adapter, "get_matrix", None) or getattr(adapter, "matrix", None)
        if gm is None or not callable(gm):
            raise RuntimeError(
                f"Adapter {type(adapter).__name__} exposes no get_matrix"
            )

        origins = _as_plain_coords(req.origins)
        dests = _as_plain_coords(req.destinations or req.origins)
        sig = inspect.signature(gm)
        params = list(sig.parameters.keys())[1:]  # skip 'self'
        kwargs: Dict[str, Any] = {}
        if "mode" in sig.parameters:
            kwargs["mode"] = req.mode
        if "parameters" in sig.parameters:
            kwargs["parameters"] = req.parameters

        # Try common shapes in order of likelihood; fall back gracefully.
        try:
            if params and params[0] in ("request", "req") and len(params) == 1:
                result = gm(req)
            elif (
                len(params) >= 2
                and params[0] in ("origins", "sources")
                and params[1] == "destinations"
            ):
                result = gm(origins, dests, **kwargs)
            elif "coordinates" in params:  # e.g., osm_graph
                result = gm(origins, **kwargs)  # coordinates := origins
            else:
                # Try request-first; if bad arity, fall back to (origins,dests)
                try:
                    result = gm(req)
                except TypeError:
                    result = gm(origins, dests, **kwargs)
        except TypeError:
            # Final fallback with explicit keywords (for keyword-only signatures)
            if "coordinates" in params:
                result = gm(coordinates=origins, **kwargs)
            else:
                result = gm(origins=origins, destinations=dests, **kwargs)

        if asyncio.iscoroutine(result):
            result = await result

        if not isinstance(result, MatrixResult):
            result = MatrixResult(**result)

        return {"status": "success", "data": {"matrix": result.model_dump()}}

    except Exception as e:
        raise HTTPException(
            500, detail={"status": "error", "message": f"Internal server error: {e}"}
        )


# ───────────────────────── simple ORS entrypoint (coords only) ─────────────────────────


def _mk_key(body: ORSMatrixBody) -> str:
    o = ";".join(f"{c.lon:.6f},{c.lat:.6f}" for c in body.origins)
    dsrc = body.destinations or body.origins
    d = ";".join(f"{c.lon:.6f},{c.lat:.6f}" for c in dsrc)
    return f"ors|{body.mode}|{o}|{d}|{tuple(sorted(body.parameters.items()))}"


@router.post(
    "/distance-matrix/ors",
    summary="Compute a distance/duration matrix via OpenRouteService (coords-only request)",
)
async def ors_matrix(body: ORSMatrixBody):
    api_key = os.getenv("ORS_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500, detail="ORS not configured (missing ORS_API_KEY)."
        )

    key = _mk_key(body)
    hit = ors_matrix_cache.get(key)
    if hit is not None:
        return hit  # cached response dict

    try:
        adapter = ORSDistanceMatrixAdapter(api_key=api_key)

        # Build internal MatrixRequest
        req = MatrixRequest(
            adapter="openrouteservice",
            origins=[c.model_dump() for c in body.origins],
            destinations=[c.model_dump() for c in (body.destinations or body.origins)],
            mode=body.mode,
            parameters=body.parameters,
        )

        result = adapter.get_matrix(req)
        if asyncio.iscoroutine(result):
            result = await result
        if not isinstance(result, MatrixResult):
            result = MatrixResult(**result)

        resp = {
            "status": "success",
            "data": {
                "matrix": {"distances": result.distances, "durations": result.durations}
            },
        }
        ors_matrix_cache.set(key, resp)
        return resp

    except DistanceMatrixRequestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")
