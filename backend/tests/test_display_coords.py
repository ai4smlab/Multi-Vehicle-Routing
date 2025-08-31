# backend/tests/test_display_coords.py
from core.coords import add_display_lonlat_from_euclidean


def test_add_display_lonlat_from_euclidean():
    wps = [{"id": "0", "x": 0, "y": 0}, {"id": "1", "x": 10, "y": 0}]
    add_display_lonlat_from_euclidean(
        wps, anchor_lon=50.0, anchor_lat=26.5, scale_km=10
    )
    assert "lon" in wps[0] and "lat" in wps[0]
    assert wps[0]["lon"] != wps[1]["lon"]  # non-zero extent
