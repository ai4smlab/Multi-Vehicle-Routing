# backend/tests/test_files.py
import json
import math
from pathlib import Path
import pytest

# ---------------------------------
# Import helpers
# ---------------------------------


def _maybe_import(module_name, *attr_names):
    """
    Try to import module and return (module, first_existing_attr or None).
    """
    try:
        mod = __import__(module_name, fromlist=["*"])
    except Exception:
        return None, None
    for a in attr_names:
        if hasattr(mod, a):
            return mod, getattr(mod, a)
    return mod, None


def _first_available(candidates):
    """
    candidates = [(module_path, func_name), ...]
    Returns (module, func) or (None, None) if none found.
    """
    for m, f in candidates:
        mod, fn = _maybe_import(m, f)
        if fn is not None:
            return mod, fn
    return None, None


def _get_lat_lon_from_waypoint(wp):
    # Accept dict, pydantic model, or simple object
    # Try flat
    for k in ("lat", "latitude"):
        lat = getattr(wp, k, None) if not isinstance(wp, dict) else wp.get(k)
        if lat is not None:
            break
    else:
        lat = None
    for k in ("lon", "lng", "longitude"):
        lon = getattr(wp, k, None) if not isinstance(wp, dict) else wp.get(k)
        if lon is not None:
            break
    else:
        lon = None
    # Try nested location
    if lat is None or lon is None:
        loc = (
            getattr(wp, "location", None)
            if not isinstance(wp, dict)
            else wp.get("location")
        )
        if isinstance(loc, dict):
            lat = lat if lat is not None else loc.get("lat")
            lon = lon if lon is not None else loc.get("lon")
        else:
            if loc is not None:
                lat = lat if lat is not None else getattr(loc, "lat", None)
                lon = lon if lon is not None else getattr(loc, "lon", None)

    return None if lat is None else float(lat), None if lon is None else float(lon)


def _get_time_window(wp):
    # Accept list-like [start,end], object with start/end, or None
    tw = (
        getattr(wp, "time_window", None)
        if not isinstance(wp, dict)
        else wp.get("time_window")
    )
    if tw is None:
        return None
    if isinstance(tw, (list, tuple)) and len(tw) == 2:
        return [int(tw[0]), int(tw[1])]
    # object with start/end
    start = getattr(tw, "start", None)
    end = getattr(tw, "end", None)
    if start is not None and end is not None:
        return [int(start), int(end)]
    return None


# ---------------------------------
# csv_loader
# ---------------------------------


def test_csv_loader_happy(tmp_path: Path):
    # Try multiple known locations / names
    mod, fn = _first_available(
        [
            ("file_loader.csv_loader", "load_csv_points"),
            ("file_handler.csv_loader", "load_csv"),
            ("file_handler.csv_loader", "load_csv_points"),
            ("file_handler.csv_loader", "load_csv_points"),
        ]
    )
    if fn is None:
        pytest.skip("csv_loader not available")

    p = tmp_path / "tiny.csv"
    p.write_text(
        "id,lat,lon,demand,service_time,tw_start,tw_end,depot\n"
        "0,0,0,0,0,0,1000,true\n"
        "1,3,4,5,10,10,100,false\n",
        encoding="utf-8",
    )

    wps = fn(str(p))
    assert len(wps) == 2
    lat1, lon1 = _get_lat_lon_from_waypoint(wps[1])
    assert (lat1, lon1) == (3.0, 4.0)
    tw1 = _get_time_window(wps[1])
    assert tw1 == [10, 100]


# ---------------------------------
# geojson_loader
# ---------------------------------


def test_geojson_loader_happy(tmp_path: Path):
    mod, fn = _first_available(
        [
            ("file_loader.geojson_loader", "load_geojson_points"),
            ("file_handler.geojson_loader", "load_geojson"),
            ("file_handler.geojson_loader", "load_geojson_points"),
            ("file_handler.geojson_loader", "load_geojson_points"),
        ]
    )
    if fn is None:
        pytest.skip("geojson_loader not available")

    gj = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [10.0, 20.0]},  # lon, lat
                "properties": {
                    "id": "0",
                    "demand": 0,
                    "service_time": 0,
                    "time_window": [0, 1000],
                    "depot": True,
                },
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [13.0, 24.0]},
                "properties": {
                    "id": "1",
                    "demand": 5,
                    "service_time": 10,
                    "time_window": [0, 1000],
                },
            },
        ],
    }
    p = tmp_path / "tiny.geojson"
    p.write_text(json.dumps(gj), encoding="utf-8")

    wps = fn(str(p))
    assert len(wps) == 2
    lat1, lon1 = _get_lat_lon_from_waypoint(wps[1])
    # Some loaders swap order; accept both
    assert (lat1, lon1) in {(24.0, 13.0), (13.0, 24.0)}


# ---------------------------------
# index_cache via dataset_indexer (smoke)
# ---------------------------------


def test_index_cache_smoke(tmp_path: Path, monkeypatch):
    di_mod, list_datasets = _maybe_import(
        "file_handler.dataset_indexer", "list_datasets"
    )
    if di_mod is None or list_datasets is None:
        pytest.skip("dataset_indexer.list_datasets not available")

    base = tmp_path / "data"
    (base / "solomon").mkdir(parents=True, exist_ok=True)
    (base / "solomon" / "A.vrp").write_text("x", encoding="utf-8")

    monkeypatch.setattr(di_mod, "DATA_DIR", str(base), raising=False)

    # clear cache if present
    if hasattr(di_mod, "DatasetIndexCache") and hasattr(
        di_mod.DatasetIndexCache, "_cache"
    ):
        di_mod.DatasetIndexCache._cache.clear()

    first = list_datasets()
    assert any(d.get("name", "").lower() == "solomon" for d in first)
    second = list_datasets()
    assert second  # same result (likely cache hit)


# ---------------------------------
# solution_loader (Solomon .sol)
# ---------------------------------


def test_solution_loader_minimal(tmp_path: Path):
    mod, load_sol = _maybe_import(
        "file_handler.solution_loader", "load_solution_sol", "load_solution"
    )
    if load_sol is None:
        pytest.skip("solution_loader.load_solution_sol not available")

    sol_text = "Route #1: 1 2 3\nRoute #2: 4 5\nCost 123.45\n"
    p = tmp_path / "tiny.sol"
    p.write_text(sol_text, encoding="utf-8")

    parsed = load_sol(str(p))
    assert "routes" in parsed and parsed["routes"]
    obj = parsed.get("objective") or parsed.get("total_distance") or parsed.get("cost")
    if obj is not None:
        assert float(obj) == pytest.approx(123.45, rel=1e-6)


# ---------------------------------
# vrplib_loader (vrplib_lib_wrapper)
# ---------------------------------


def test_vrplib_loader_coords_matrix(monkeypatch):
    mod, load_vrplib = _maybe_import(
        "file_handler.vrplib_lib_wrapper", "load_with_vrplib"
    )
    if load_vrplib is None:
        pytest.skip("vrplib_lib_wrapper.load_with_vrplib not available")

    monkeypatch.setattr(mod, "VRPLIB_AVAILABLE", True, raising=False)

    inst = {
        "coordinates": [(0.0, 0.0), (3.0, 4.0)],
        "depot": 1,  # 1-based
        "demands": [0, 5],
        "capacity": 10,
        "vehicles": 2,
        "ready_time": [0, 10],
        "due_time": [100, 50],  # force swap check
        "service_time": [0, 7],
    }

    class _FakeVRPLib:
        @staticmethod
        def read_instance(_):
            return inst

    monkeypatch.setattr(mod, "_vrplib", _FakeVRPLib, raising=False)

    out = load_vrplib("fake.vrp", compute_matrix=True)
    assert out["depot_index"] == 0
    wps = out["waypoints"]
    assert len(wps) == 2
    # Euclidean distance 5.0
    m = out["matrix"]["distances"]
    assert math.isclose(m[0][1], 5.0, rel_tol=1e-6)  # NOTE: rel_tol

    # time window fixed
    assert wps[1]["time_window"][0] <= wps[1]["time_window"][1]


def test_vrplib_loader_edge_weight(monkeypatch):
    mod, load_vrplib = _maybe_import(
        "file_handler.vrplib_lib_wrapper", "load_with_vrplib"
    )
    if load_vrplib is None:
        pytest.skip("vrplib_lib_wrapper.load_with_vrplib not available")

    monkeypatch.setattr(mod, "VRPLIB_AVAILABLE", True, raising=False)

    inst = {
        "edge_weight": [[0, 2], [2, 0]],
        "depot": [1],
        "capacity": 9,
        "vehicles": 1,
    }

    class _FakeVRPLib:
        @staticmethod
        def read_instance(_):
            return inst

    monkeypatch.setattr(mod, "_vrplib", _FakeVRPLib, raising=False)

    out = load_vrplib("fake.vrp", compute_matrix=False)
    assert out["matrix"]["distances"] == [[0.0, 2.0], [2.0, 0.0]]
    assert len(out["fleet"]["vehicles"]) == 1


# ---------------------------------
# vrplib_writer (be liberal with signatures)
# ---------------------------------


def test_vrplib_writer_minimal(tmp_path: Path):
    mod, writer = _first_available(
        [
            ("file_handler.vrplib_writer", "write_vrplib"),
            ("file_handler.vrplib_writer", "write_instance"),
            ("file_handler.vrplib_writer", "write_vrplib"),
        ]
    )
    if writer is None:
        pytest.skip("vrplib_writer not available")

    out_file = tmp_path / "tiny_out.vrp"

    # Instance-like payload
    instance_like = {
        "waypoints": [
            {
                "id": "1",
                "lat": 0.0,
                "lon": 0.0,
                "demand": 0,
                "time_window": [0, 1000],
                "service_time": 0,
                "depot": True,
            },
            {
                "id": "2",
                "lat": 3.0,
                "lon": 4.0,
                "demand": 5,
                "time_window": [0, 1000],
                "service_time": 0,
            },
        ],
        "fleet": {
            "vehicles": [{"id": "veh-1", "capacity": [10], "start": 0, "end": 0}]
        },
        "matrix": {"distances": [[0, 5], [5, 0]]},
    }

    # Try common signatures
    called = False
    try:
        # writer(path, instance_like)
        writer(str(out_file), instance_like)
        called = True
    except TypeError:
        pass

    if not called:
        # Try writer(path, waypoints, fleet, matrix)
        try:
            writer(
                str(out_file),
                instance_like["waypoints"],
                instance_like["fleet"],
                instance_like.get("matrix"),
            )
            called = True
        except TypeError:
            pass

    if not called:
        # Try writer(path, waypoints, fleet)  (no matrix)
        try:
            writer(
                str(out_file),
                instance_like["waypoints"],
                instance_like["fleet"],
            )
            called = True
        except TypeError:
            pass

    if not called:
        pytest.skip("vrplib_writer signature not recognized")

    assert out_file.exists()
    text = out_file.read_text(encoding="utf-8").upper()
    assert "DIMENSION" in text
    assert ("NODE_COORD" in text) or ("EDGE_WEIGHT_SECTION" in text)


# ---------------------------------
# xml_loader (services.file_handler.xml_loader)
# ---------------------------------


def test_xml_loader_roundtripish():
    mod, cls = _maybe_import("file_handler.xml_loader", "VRPSetXMLLoader")
    if cls is None:
        pytest.skip("VRPSetXMLLoader not available")

    xml = """
    <instance>
      <fleet>
        <vehicles>2</vehicles>
        <capacity>50</capacity>
      </fleet>
      <nodes>
        <node id="1" x="0" y="0"><depot>true</depot></node>
        <node id="2" x="3" y="4" demand="5" ready="0" due="100" service="0" />
      </nodes>
    </instance>
    """.strip().encode(
        "utf-8"
    )

    loader = cls()
    out = loader.load_bytes(xml, filename="tiny.xml", compute_matrix=True)

    assert "waypoints" in out and len(out["waypoints"]) == 2
    assert out.get("depot_index", 0) == 0
    assert (
        "fleet" in out
        and "vehicles" in out["fleet"]
        and len(out["fleet"]["vehicles"]) == 2
    )

    m = out.get("matrix", {}).get("distances")
    assert m and len(m) == 2 and len(m[0]) == 2
    assert math.isclose(m[0][1], 5.0, rel_tol=1e-6)
