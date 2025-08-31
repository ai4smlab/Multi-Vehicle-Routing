# api/files_routes.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
import shutil
import os

# parse/write helpers (reuse your existing loaders/writers)
from file_handler.file_factory import load_any  # or your central parse shim
from file_handler.vrplib_writer import write_vrplib  # your existing writer

# ---- Root directory for custom files ----
try:
    from config import get_settings  # type: ignore

    CUSTOM_ROOT = Path(get_settings().CUSTOM_DATA_DIR).resolve()
except Exception:
    # fallback to Project/backend/data/custom_data
    CUSTOM_ROOT = (
        Path(__file__).resolve().parents[1] / "data" / "custom_data"
    ).resolve()

CUSTOM_ROOT.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/files", tags=["files"])


# ---------- Models ----------


class FileEntry(BaseModel):
    path: str  # relative to CUSTOM_ROOT
    name: str
    size: int
    mtime: float
    kind: str  # "file" | "dir"
    ext: Optional[str] = None


class ListResponse(BaseModel):
    dataset: str
    cwd: str
    total: int
    files: List[FileEntry]


class FindResponse(BaseModel):
    dataset: str
    q: Optional[str]
    exts: Optional[List[str]]
    total: int
    files: List[FileEntry]


class ParseRequest(BaseModel):
    path: str  # relative path under CUSTOM_ROOT
    kind: Optional[str] = (
        None  # "csv" | "geojson" | "vrplib" | "xml" | "solomon" | None (auto)
    )
    options: Optional[dict] = None  # passed to loader


class WriteVRPLIBRequest(BaseModel):
    path: str  # e.g. "exports/out.vrp"
    waypoints: list
    fleet: dict
    depot_index: int = 0
    matrix: Optional[dict] = None
    options: Optional[dict] = None


# ---------- Helpers ----------


def _safe_join(rel: str) -> Path:
    """
    Prevent path traversal. Returns absolute path within CUSTOM_ROOT or raises 400.
    """
    rel = rel.strip().lstrip("/\\")
    p = (CUSTOM_ROOT / rel).resolve()
    if CUSTOM_ROOT not in p.parents and p != CUSTOM_ROOT:
        raise HTTPException(
            status_code=400, detail="Invalid path (outside custom_data)"
        )
    return p


def _entry(p: Path) -> FileEntry:
    stat = p.stat()
    kind = "dir" if p.is_dir() else "file"
    ext = p.suffix.lower() if p.is_file() else None
    return FileEntry(
        path=str(p.relative_to(CUSTOM_ROOT)),
        name=p.name,
        size=stat.st_size,
        mtime=stat.st_mtime,
        kind=kind,
        ext=ext,
    )


def _walk(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        for name in dirnames:
            yield d / name
        for name in filenames:
            yield d / name


# ---------- Endpoints ----------


@router.get("/datasets")
def list_datasets():
    # For now, one logical dataset backed by CUSTOM_ROOT
    return [{"name": "custom_data", "path": str(CUSTOM_ROOT)}]


@router.get("/list", response_model=ListResponse)
def list_files(
    dataset: str = Query(default="custom_data"),
    cwd: str = Query(default=""),
    q: Optional[str] = Query(default=None),
    exts: Optional[str] = Query(
        default=None, description="Comma-separated (e.g. .csv,.geojson)"
    ),
    limit: int = 50,
    offset: int = 0,
    sort: str = "name",
    order: str = "asc",
):
    if dataset != "custom_data":
        raise HTTPException(404, "Unknown dataset")

    base = _safe_join(cwd or "")
    if not base.exists():
        raise HTTPException(404, "Directory not found")

    candidates = []
    for child in sorted(base.iterdir()):
        if q and q.lower() not in child.name.lower():
            continue
        if exts:
            allowed = {e.strip().lower() for e in exts.split(",") if e.strip()}
            if child.is_file() and child.suffix.lower() not in allowed:
                continue
        candidates.append(child)

    reverse = order.lower() == "desc"
    if sort == "name":
        candidates.sort(key=lambda p: p.name.lower(), reverse=reverse)
    elif sort == "size":
        candidates.sort(
            key=lambda p: (p.stat().st_size if p.is_file() else -1), reverse=reverse
        )
    elif sort == "mtime":
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=reverse)

    total = len(candidates)
    page = candidates[offset : offset + limit]
    return ListResponse(
        dataset="custom_data",
        cwd=str(base.relative_to(CUSTOM_ROOT)) if base != CUSTOM_ROOT else "",
        total=total,
        files=[_entry(p) for p in page],
    )


@router.get("/find", response_model=FindResponse)
def find_files(
    dataset: str = Query(default="custom_data"),
    q: Optional[str] = None,
    exts: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    if dataset != "custom_data":
        raise HTTPException(404, "Unknown dataset")
    allowed = None
    if exts:
        allowed = {e.strip().lower() for e in exts.split(",") if e.strip()}

    all_paths = []
    for p in _walk(CUSTOM_ROOT):
        if q and q.lower() not in p.name.lower():
            continue
        if allowed and p.is_file() and p.suffix.lower() not in allowed:
            continue
        all_paths.append(p)

    total = len(all_paths)
    page = all_paths[offset : offset + limit]
    return FindResponse(
        dataset="custom_data",
        q=q,
        exts=(list(allowed) if allowed else None),
        total=total,
        files=[_entry(p) for p in page],
    )


@router.post("/upload")
def upload_file(
    file: UploadFile = File(...),
    subdir: str = Form(default=""),
    overwrite: bool = Form(default=False),
):
    target_dir = _safe_join(subdir or "")
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / file.filename
    target = target.resolve()

    if target.exists() and not overwrite:
        raise HTTPException(409, "File already exists (set overwrite=true)")

    with target.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    return {"path": str(target.relative_to(CUSTOM_ROOT)), "size": target.stat().st_size}


@router.delete("/delete")
def delete_file(path: str):
    p = _safe_join(path)
    if not p.exists():
        raise HTTPException(404, "Not found")
    if p.is_dir():
        shutil.rmtree(p)
    else:
        p.unlink()
    return {"status": "ok"}


@router.post("/parse")
def parse_file(req: ParseRequest):
    p = _safe_join(req.path)
    if not p.exists() or not p.is_file():
        raise HTTPException(404, "File not found")
    try:
        data = load_any(str(p), kind=req.kind, **(req.options or {}))
        # normalize wrapper
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(400, detail=f"Parse failed: {e}")


@router.post("/write/raw")
def write_raw(
    path: str = Form(...),
    content: str = Form(...),
    overwrite: bool = Form(default=False),
):
    p = _safe_join(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists() and not overwrite:
        raise HTTPException(409, "File exists")
    p.write_text(content, encoding="utf-8")
    return {"path": str(p.relative_to(CUSTOM_ROOT)), "size": p.stat().st_size}


@router.post("/write/vrplib")
def write_vrplib_file(req: WriteVRPLIBRequest):
    p = _safe_join(req.path)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Your writer expects individual fields; pass through
        write_vrplib(
            out_path=str(p),
            waypoints=req.waypoints,
            fleet=req.fleet,  # ← ensure your writer signature matches
            depot_index=req.depot_index,
            matrix=req.matrix,
            **(req.options or {}),
        )
        return {"path": str(p.relative_to(CUSTOM_ROOT)), "size": p.stat().st_size}
    except TypeError as te:
        raise HTTPException(400, detail=f"Writer signature mismatch: {te}")
    except Exception as e:
        raise HTTPException(400, detail=f"Write failed: {e}")
