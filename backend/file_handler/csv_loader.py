import csv
from models.waypoints import Waypoint


def _b(s):
    return str(s).strip().lower() in ("1", "true", "yes", "y", "t")


def load_csv_points(path: str) -> list[Waypoint]:
    wps: list[Waypoint] = []
    with open(path, newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for i, row in enumerate(rdr, start=1):
            # tolerate x/y or lon/lat or lng/lat
            lat = row.get("lat")
            lon = row.get("lon", row.get("lng"))
            if lat is None or lon is None:
                lat = row.get("y")
                lon = row.get("x")
            if lat is None or lon is None:
                raise ValueError("CSV must have lat/lon (or lng) or x/y columns.")

            wps.append(
                Waypoint(
                    id=str(row.get("id", i)),
                    lat=float(lat),
                    lon=float(lon),
                    demand=int(row.get("demand", 0) or 0),
                    service_time=int(row.get("service_time", 0) or 0),
                    time_window=(
                        [int(row["tw_start"]), int(row["tw_end"])]
                        if row.get("tw_start") and row.get("tw_end")
                        else None
                    ),
                    depot=_b(row.get("depot", "false")),
                )
            )
    return wps
