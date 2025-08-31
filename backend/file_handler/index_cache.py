# services/file_handler/index_cache.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Any, Dict, Optional
import os
import time
import threading


@dataclass
class FileEntry:
    relpath: str
    size: int
    mtime: float
    ext: str


class DatasetIndexCache:
    """Simple in-process cache of file metadata per dataset folder."""

    _lock = threading.Lock()
    _cache: Dict[str, Tuple[float, List[FileEntry]]] = {}
    _ttl = 300  # seconds

    @classmethod
    def get_index(cls, root: Path, force: bool = False) -> List[FileEntry]:
        key = str(root.resolve())
        now = time.time()
        with cls._lock:
            if (
                not force
                and key in cls._cache
                and (now - cls._cache[key][0] < cls._ttl)
            ):
                return cls._cache[key][1]

        entries: List[FileEntry] = []
        # os.walk + DirEntry.stat is fast enough; avoid extra string ops inside the loop
        for dirpath, filenames in os.walk(root):
            dp = Path(dirpath)
            for name in filenames:
                p = dp / name
                try:
                    st = p.stat()
                except OSError:
                    continue
                entries.append(
                    FileEntry(
                        relpath=str(p.relative_to(root)),
                        size=st.st_size,
                        mtime=st.st_mtime,
                        ext=p.suffix.lower(),
                    )
                )

        with cls._lock:
            cls._cache[key] = (now, entries)
        return entries

    @staticmethod
    def to_dict(entry: Any) -> Optional[Dict[str, Any]]:
        """Robustly convert an index entry (object or dict) into a plain dict."""
        if entry is None:
            return None

        # Try attribute access first, then dict access, then derive.
        def _get(e, attr, key=None, default=None):
            if hasattr(e, attr):
                return getattr(e, attr)
            if isinstance(e, dict) and key:
                return e.get(key, default)
            return default

        relpath = _get(entry, "relpath", "relpath")
        if isinstance(relpath, Path):
            relpath = relpath.as_posix()
        if not relpath:
            # last resort – string form
            relpath = str(entry)

        size = _get(entry, "size", "size")
        mtime = _get(entry, "mtime", "mtime")
        ext = _get(entry, "ext", "ext")
        if not ext and relpath:
            ext = Path(relpath).suffix.lower()

        return {
            "relpath": relpath,
            "size": size,
            "mtime": mtime,
            "ext": ext,
        }
