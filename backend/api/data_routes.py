# backend/api/data_routes.py
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import re

from data_acquisition.open_source.openstreetmap import (
    nodes_by_tag_in_bbox,
    nodes_by_tag_in_place,
    pois_by_tag_in_place,
)

router = APIRouter(prefix="/osm", tags=["osm"])


def _clean_value_and_regex(v: str) -> tuple[str, bool]:
    if v is None:
        return "", False
    s = str(v).strip()
    is_rx = False
    if s.startswith("~"):
        is_rx = True
        s = s[1:].strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        s = s[1:-1]
    if not is_rx and re.search(r"[|.*+?()[\]{}\\]", s):
        is_rx = True
    return s, is_rx


@router.get("/pois")
def get_pois_bbox(
    south: float,
    west: float,
    north: float,
    east: float,
    key: str,
    value: str,
    regex: bool = Query(False),
    timeout: int = Query(120, ge=1, le=600),
    limit: Optional[int] = Query(None, ge=1, le=5000),
):
    clean, rx_auto = _clean_value_and_regex(value)
    use_rx = bool(regex) or rx_auto
    return nodes_by_tag_in_bbox(
        (south, west, north, east),
        key,
        clean,
        regex=use_rx,
        timeout=timeout,
        limit=limit,
    )


@router.get("/pois/by-place")
def get_pois_place(
    place: str = Query(...),
    key: str = Query(...),
    value: str = Query(...),
    include_ways: bool = Query(True),
    include_relations: bool = Query(True),
    regex: bool = Query(False),
    timeout: int = Query(120, ge=1, le=600),
    limit: Optional[int] = Query(None, ge=1, le=5000),
):
    clean, rx_auto = _clean_value_and_regex(value)
    use_rx = bool(regex) or rx_auto
    if not include_ways and not include_relations:
        return nodes_by_tag_in_place(
            place, key, clean, regex=use_rx, timeout=timeout, limit=limit
        )
    return pois_by_tag_in_place(
        place,
        key,
        clean,
        include_ways=include_ways,
        include_relations=include_relations,
        regex=use_rx,
        timeout=timeout,
        limit=limit,
    )


@router.get("/pois/auto")
def get_pois_auto(
    key: str,
    value: str,
    place: Optional[str] = Query(None),
    south: Optional[float] = None,
    west: Optional[float] = None,
    north: Optional[float] = None,
    east: Optional[float] = None,
    include_ways: bool = Query(True),
    include_relations: bool = Query(True),
    timeout: int = Query(120, ge=1, le=600),
    limit: Optional[int] = Query(None, ge=1, le=5000),
):
    clean, rx_auto = _clean_value_and_regex(value)
    has_place = place is not None
    has_bbox = all(v is not None for v in (south, west, north, east))
    if has_place == has_bbox:
        raise HTTPException(
            status_code=400,
            detail="Provide either `place` OR (south, west, north, east).",
        )

    if has_place:
        return pois_by_tag_in_place(
            place=place,
            key=key,
            value=clean,
            include_ways=include_ways,
            include_relations=include_relations,
            regex=rx_auto,
            timeout=timeout,
            limit=limit,
        )

    return nodes_by_tag_in_bbox(
        (south, west, north, east),
        key=key,
        value=clean,
        regex=rx_auto,
        timeout=timeout,
        limit=limit,
    )
