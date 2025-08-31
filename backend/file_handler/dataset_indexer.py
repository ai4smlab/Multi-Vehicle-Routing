# file_handler/dataset_indexer.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Iterable
import os

# If you leave this nonempty, it can hide datasets during tests.
# Make it empty to include all subfolders except the explicit excludes.
BENCHMARK_INCLUDE_FOLDERS: set[str] = set()
BENCHMARK_EXCLUDE_FOLDERS = {
    "custom_examples",
    "real_world",
    "test_files",
    "custom_data",
}

INSTANCE_EXTS = {".vrp", ".xml", ".txt"}
SOLUTION_EXTS = {".sol", ".xml", ".txt"}
DEFAULT_EXTS = {".vrp", ".xml", ".txt", ".sol", ".json", ".geojson", ".csv"}

DATA_DIR = os.getenv("DATA_DIR", "./backend/data")


def _candidate_roots() -> list[Path]:
    primary = _data_dir()
    roots = [primary]
    default_root = Path("./backend/data").resolve()
    if default_root != primary and default_root.exists():
        roots.append(default_root)
    return roots


def _data_dir() -> Path:
    """Resolve datasets root at call-time (honors monkeypatched module attr first)."""
    # Prefer the module-level variable (tests monkeypatch this), then fall back to env, then default.
    raw = globals().get("DATA_DIR")
    if not raw:
        raw = os.getenv("DATA_DIR", "./backend/data")
    return Path(str(raw)).resolve()


def get_data_dir() -> Path:
    """Public accessor for routes and other modules."""
    return _data_dir()


def set_data_dir(path: str | Path) -> Path:
    """Helper for tests; updates env and module attr."""
    p = Path(path).resolve()
    os.environ["DATA_DIR"] = str(p)
    # keep as str to match how tests monkeypatch
    globals()["DATA_DIR"] = str(p)
    return p


@dataclass
class FileEntry:
    name: str
    relpath: str
    abspath: str
    size: int

    @classmethod
    def from_path(cls, root: Path, p: Path) -> "FileEntry":
        return cls(
            name=p.name,
            relpath=str(p.relative_to(root)),
            abspath=str(p),
            size=p.stat().st_size if p.exists() else 0,
        )


def _iter_datasets() -> List[Path]:
    items: List[Path] = []
    seen: set[str] = set()
    for root in _candidate_roots():
        if not root.exists():
            continue
        for child in root.iterdir():
            if not child.is_dir():
                continue
            name_l = child.name.lower()
            if name_l in BENCHMARK_EXCLUDE_FOLDERS:
                continue
            if BENCHMARK_INCLUDE_FOLDERS and name_l not in BENCHMARK_INCLUDE_FOLDERS:
                continue
            if name_l in seen:
                continue
            items.append(child)
            seen.add(name_l)
    return sorted(items, key=lambda p: p.name.lower())


def list_datasets() -> List[Dict]:
    return [{"name": ds.name, "path": str(ds)} for ds in _iter_datasets()]


def _canonicalize_dataset(name: str) -> Optional[Path]:
    name_l = name.lower()
    for ds in _iter_datasets():
        if ds.name.lower() == name_l:
            return ds
    return None


def ensure_index(dataset: str) -> None:
    """
    Back-compat shim. We don't keep a cache here, but calling list_files once
    mirrors the old behavior (warm/validate).
    """
    try:
        _ = list_files(
            dataset=dataset,
            limit=1,
            offset=0,
            exts=list(DEFAULT_EXTS),
            q=None,
            kind=None,
        )
    except Exception:
        # don't fail callers just because the dataset is empty/missing
        pass


def _scan_files(root: Path, exts: Optional[Iterable[str]] = None) -> List[FileEntry]:
    exts_l = {e.lower() for e in exts} if exts else None
    out: List[FileEntry] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if exts_l is not None and p.suffix.lower() not in exts_l:
            continue
        out.append(FileEntry.from_path(root, p))
    return out


def normalize_dataset_name(name: str) -> str:
    lookup = {d["name"].lower(): d["name"] for d in list_datasets()}
    return lookup.get(name.lower(), name)


def list_files(
    dataset: str,
    limit: int = 100,
    offset: int = 0,
    sort: str = "name",
    order: str = "asc",
    q: Optional[str] = None,
    exts: Optional[List[str]] = None,
    kind: Optional[str] = None,
) -> Dict:
    ds = _canonicalize_dataset(dataset)
    if not ds:
        return {"items": [], "total": 0, "limit": limit, "offset": offset}

    suffix_filter = None
    if kind == "instances":
        suffix_filter = INSTANCE_EXTS
    elif kind == "solutions":
        suffix_filter = SOLUTION_EXTS

    exts_use = set(exts) if exts else DEFAULT_EXTS
    if suffix_filter is not None:
        exts_use = exts_use & set(suffix_filter)

    files = _scan_files(ds, exts=exts_use)
    if q:
        ql = q.lower()
        files = [f for f in files if ql in f.name.lower() or ql in f.relpath.lower()]

    reverse = order.lower() == "desc"
    files.sort(
        key=(lambda f: f.size) if sort == "size" else (lambda f: f.name.lower()),
        reverse=reverse,
    )

    total = len(files)
    window = files[offset : offset + limit]
    return {
        "items": [asdict(f) for f in window],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def find_pair(dataset: str, name: str) -> Dict:
    """
    Find an instance (.vrp/.xml/.txt) and optional solution (.sol) by base name (case-insensitive)
    anywhere under the dataset directory (subfolders like 'instances/' are OK).

    Returns normalized dicts with at least {name, path, relpath, dataset, kind, size, ext}.
    """
    ds = _canonicalize_dataset(dataset)
    if not ds:
        return {"instance": None, "solution": None}

    # accept both "c101" and "c101.vrp"
    from pathlib import Path

    target = Path(name).stem.lower()
    instance: Optional[FileEntry] = None
    solution: Optional[FileEntry] = None

    for p in ds.rglob("*"):
        if not p.is_file():
            continue
        stem = p.stem.lower()
        if stem != target:
            continue
        suf = p.suffix.lower()
        if suf in INSTANCE_EXTS and instance is None:
            instance = FileEntry.from_path(ds, p)
        elif suf in SOLUTION_EXTS and solution is None:
            solution = FileEntry.from_path(ds, p)
        if instance and solution:
            break

    # normalize to include "path" alias
    def _pub(fe: Optional[FileEntry], kind: str) -> Optional[Dict]:
        if not fe:
            return None
        d = asdict(fe)
        d["dataset"] = ds.name
        d["kind"] = kind
        d["ext"] = Path(fe.abspath).suffix.lower()
        d["path"] = fe.abspath  # <— alias expected by tests
        return d

    return {
        "instance": _pub(instance, "instance"),
        "solution": _pub(solution, "solution"),
    }
