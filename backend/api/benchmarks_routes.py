# api/vrplib_routes.py
from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Query

from file_handler.dataset_indexer import (
    list_datasets,
    list_files,
    find_pair,
    normalize_dataset_name,
)
from file_handler.file_factory import get_loader_for_filename
from core.coords import add_display_lonlat_from_euclidean, looks_euclidean

router = APIRouter(tags=["benchmarks"])

# ---------- helpers


def _pub_item(it: Dict[str, Any]) -> Dict[str, Any]:
    name = it.get("name")
    abspath = it.get("abspath") or it.get("path")
    relpath = it.get("relpath")
    ext = (
        Path(name).suffix.lower()
        if name
        else (Path(abspath).suffix.lower() if abspath else None)
    )
    out = {
        "name": name,
        "path": abspath,
        "relpath": relpath,
        "size": it.get("size"),
        "ext": ext,
    }
    for k in ("dataset", "kind"):
        if k in it:
            out[k] = it[k]
    return {k: v for k, v in out.items() if v is not None}


# ---------- routes


@router.get("/benchmarks")
def get_benchmarks():
    return {"datasets": list_datasets()}


@router.get("/benchmarks/files")
def get_benchmark_files(
    dataset: str = Query(
        ..., description="Dataset folder name as shown by /benchmarks"
    ),
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(None),
    sort: str = Query("name", pattern="^(name|size)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    exts: Optional[str] = Query(
        None, description="Comma-separated extensions, e.g. .vrp,.xml,.sol"
    ),
    kind: Optional[str] = Query(None, description="'instances' | 'solutions' | None"),
):
    ds = normalize_dataset_name(dataset)
    ext_list = [e.strip() for e in exts.split(",")] if exts else None

    data = list_files(
        dataset=ds,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
        q=q,
        exts=ext_list,
        kind=kind,
    )

    items = [_pub_item(it) for it in data.get("items", [])]

    enriched: List[Dict[str, Any]] = []
    for it in items:
        try:
            stem = Path(it["name"]).stem
            pair = find_pair(ds, stem)
            sol = pair.get("solution")
            if sol and sol.get("path"):
                it["solution_path"] = sol["path"]
        except Exception:
            pass
        enriched.append(it)

    return {
        "items": enriched,
        "total": data.get("total", len(enriched)),
        "limit": limit,
        "offset": offset,
    }


@router.get("/benchmarks/find")
def find_instance_and_solution(dataset: str, name: str):
    ds = normalize_dataset_name(dataset)
    pair = find_pair(ds, name)
    return {
        "instance": pair.get("instance"),
        "solution": pair.get("solution"),
        "status": "success",
    }


@router.get("/benchmarks/load")
def load_instance(
    dataset: str,
    name: str,
    compute_matrix: bool = True,
    include_display: bool = Query(
        False, description="If true, add WGS84 display lon/lat synthesized from x/y"
    ),
    display_anchor: Optional[str] = Query(None, description="lon,lat (default 0,0)"),
    display_scale_km: float = Query(
        40.0, description="Extent width/height in km, centered on anchor"
    ),
):
    ds = normalize_dataset_name(dataset)
    pair = find_pair(ds, name)
    inst = pair.get("instance")
    if not inst or not inst.get("path"):
        raise HTTPException(status_code=404, detail="Instance not found")

    inst_path = inst["path"]
    try:
        loader = get_loader_for_filename(inst_path)
        data = loader(str(inst_path), compute_matrix=compute_matrix)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # --- Dual-space: synthesize display lon/lat for planar EUC_* instances ---
    if include_display and looks_euclidean(
        data.get("edge_weight_type"),
        data.get("meta"),
        data.get("waypoints"),
    ):
        anchor_lon, anchor_lat = 0.0, 0.0
        if display_anchor:
            try:
                a, b = display_anchor.split(",")
                anchor_lon, anchor_lat = float(a), float(b)
            except Exception:
                raise HTTPException(
                    status_code=400, detail="display_anchor must be 'lon,lat'"
                )
        add_display_lonlat_from_euclidean(
            data.get("waypoints", []),
            anchor_lon=anchor_lon,
            anchor_lat=anchor_lat,
            scale_km=float(display_scale_km),
            flip_y=True,
            x_field="x",
            y_field="y",
            out_lon="lon",
            out_lat="lat",
        )
        data.setdefault("meta", {}).setdefault("notes", []).append(
            f"display synthesized @ anchor=({anchor_lon},{anchor_lat}), scale_km={display_scale_km}"
        )
        data.setdefault("coordinate_spaces", {}).setdefault(
            "display", {"type": "wgs84", "fields": ["lon", "lat"]}
        )

    return {
        "status": "success",
        "instance": inst,
        "solution": pair.get("solution"),
        "instance_path": inst_path,
        "solution_path": (
            pair.get("solution", {}).get("path") if pair.get("solution") else None
        ),
        "data": data,
    }
