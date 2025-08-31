# backend/data_acquisition/open_source/openstreetmap.py
from __future__ import annotations
import time
from typing import List, Optional, Tuple, Dict, Any
import requests

DEFAULT_TIMEOUT = 120
RATE_LIMIT_SLEEP = 0.8  # friendly pause

OVERPASS_MIRRORS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def _sleep():
    time.sleep(RATE_LIMIT_SLEEP)


def _post_overpass(ql: str, *, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    last_err: Exception | None = None
    for url in OVERPASS_MIRRORS:
        _sleep()
        try:
            r = requests.post(
                url,
                data={"data": ql},
                timeout=timeout + 10,
                headers={"User-Agent": "vrp-tool/1.0"},
            )
            if r.status_code in (429, 502, 503, 504):
                last_err = RuntimeError(f"{url} -> {r.status_code} {r.text[:200]}")
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            continue
    print(
        "\n--- Overpass QL (FAILED) ---\n",
        ql,
        "\n----------------------------\n",
        flush=True,
    )
    raise RuntimeError(f"overpass_error: {last_err}")


def _build_selector(key: str, value: str, regex: bool = False) -> str:
    if value is None:
        value = ""
    v = str(value).strip()

    # existence
    if v == "*":
        return f'"{key}"'

    use_rx = regex or v.startswith("~")
    if v.startswith("~"):
        v = v[1:].strip()

    # strip surrounding quotes
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
        v = v[1:-1]

    # escape for QL
    v = v.replace("\\", "\\\\").replace('"', r"\"")

    return (f'"{key}"~"{v}"') if use_rx else (f'"{key}"="{v}"')


def _normalize_key_value(key: str, value: str) -> tuple[str, str]:
    if key == "amenity" and value == "bus_stop":
        return "highway", "bus_stop"
    return key, value


def _elements_to_fc(doc: Dict[str, Any]) -> Dict[str, Any]:
    feats: List[Dict[str, Any]] = []
    for el in doc.get("elements", []):
        etype = el.get("type")
        props = dict(el.get("tags", {}) or {})
        props["__osm_type"] = etype
        props["__id"] = el.get("id")

        lon = lat = None
        if etype == "node":
            lon = el.get("lon")
            lat = el.get("lat")
        else:
            c = el.get("center") or {}
            lon = c.get("lon")
            lat = c.get("lat")

        if lon is None or lat is None:
            continue
        feats.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
                "properties": props,
            }
        )
    return {"type": "FeatureCollection", "features": feats}


# ---------- Nominatim (place -> bbox) ----------


def place_to_bbox(place: str) -> Tuple[float, float, float, float]:
    """
    Resolve 'City, Country' (etc.) to (south, west, north, east) bbox using Nominatim.
    """
    _sleep()
    r = requests.get(
        NOMINATIM_URL,
        params={"q": place, "format": "jsonv2", "limit": 1, "addressdetails": 0},
        headers={"User-Agent": "vrp-tool/1.0"},
        timeout=20,
    )
    r.raise_for_status()
    arr = r.json()
    if not isinstance(arr, list) or not arr:
        raise RuntimeError(f"Nominatim: place not found: {place}")
    bb = arr[0].get("boundingbox")
    # boundingbox is [south, north, west, east] as strings
    if not (isinstance(bb, list) and len(bb) == 4):
        raise RuntimeError(f"Nominatim: invalid bbox for {place}")
    south = float(bb[0])
    north = float(bb[1])
    west = float(bb[2])
    east = float(bb[3])
    return (south, west, north, east)


# ------------------------------
#  Public helpers (same names)
# ------------------------------


def nodes_by_tag_in_bbox(
    bbox: Tuple[float, float, float, float],
    key: str,
    value: str,
    *,
    regex: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    (south, west, north, east) = bbox
    key, value = _normalize_key_value(key, value)
    sel = _build_selector(key, value, regex=regex)
    lim = f" {int(limit)}" if isinstance(limit, int) and limit > 0 else ""
    ql = f"""
[out:json][timeout:{timeout}];
node[{sel}]({south},{west},{north},{east});
out body qt{lim};
"""
    doc = _post_overpass(ql, timeout=timeout)
    return _elements_to_fc(doc)


def nodes_by_tag_in_place(
    place: str,
    key: str,
    value: str,
    *,
    regex: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    bbox = place_to_bbox(place)
    return nodes_by_tag_in_bbox(
        bbox, key, value, regex=regex, timeout=timeout, limit=limit
    )


def pois_by_tag_in_place(
    place: str,
    key: str,
    value: str,
    *,
    include_ways: bool = True,
    include_relations: bool = True,
    regex: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Use bbox of the place and query n/w/r in one go; centers returned for ways/relations.
    """
    (south, west, north, east) = place_to_bbox(place)

    key, value = _normalize_key_value(key, value)
    sel = _build_selector(key, value, regex=regex)
    lim = f" {int(limit)}" if isinstance(limit, int) and limit > 0 else ""

    parts = [
        "node[{sel}]({s},{w},{n},{e});".format(
            sel=sel, s=south, w=west, n=north, e=east
        )
    ]
    if include_ways:
        parts.append(
            "way[{sel}]({s},{w},{n},{e});".format(
                sel=sel, s=south, w=west, n=north, e=east
            )
        )
    if include_relations:
        parts.append(
            "relation[{sel}]({s},{w},{n},{e});".format(
                sel=sel, s=south, w=west, n=north, e=east
            )
        )

    union = "\n  ".join(parts)
    ql = f"""
[out:json][timeout:{timeout}];
(
  {union}
);
out tags center qt{lim};
"""
    doc = _post_overpass(ql, timeout=timeout)
    return _elements_to_fc(doc)
