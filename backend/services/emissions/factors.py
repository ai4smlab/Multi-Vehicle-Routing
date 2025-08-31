# services/emissions/factors.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# We use pandas if available for XLSX parsing; otherwise we’ll raise a clear error.
try:
    import pandas as pd  # type: ignore
except Exception:
    pd = None  # type: ignore


@dataclass(frozen=True)
class SpeedBin:
    min_kmh: float  # inclusive
    max_kmh: float  # exclusive
    ef_g_per_km: float


Key = Tuple[str, str, str]  # (vehicle_type, fuel, scope)


class GHGFactors:
    """
    Stores per-km factors and (optional) speed-binned factors in grams CO2e per km.
    Keys are normalized lower-case tuples: (vehicle_type, fuel, scope) where scope ∈ {"TTW","WTW"}.
    """

    def __init__(
        self,
        per_km_table: Optional[Dict[Key, float]] = None,
        speed_tables: Optional[Dict[Key, List[SpeedBin]]] = None,
        name: str = "custom",
    ) -> None:
        self.name = name
        self.per_km_table: Dict[Key, float] = per_km_table or {}
        self.speed_tables: Dict[Key, List[SpeedBin]] = speed_tables or {}

    @staticmethod
    def _norm_key(vehicle_type: str, fuel: str, scope: str) -> Key:
        return (
            vehicle_type.strip().lower(),
            fuel.strip().lower(),
            scope.strip().upper(),
        )

    # ---------- Public API used by your calculator ----------
    def has_speed_bins(self, vehicle_type: str, fuel: str, scope: str) -> bool:
        key = self._norm_key(vehicle_type, fuel, scope)
        return key in self.speed_tables and len(self.speed_tables[key]) > 0

    def per_km(self, vehicle_type: str, fuel: str, scope: str) -> float:
        """
        Returns grams CO2e per km. If not present, tries to estimate from speed bins (mean).
        """
        key = self._norm_key(vehicle_type, fuel, scope)
        if key in self.per_km_table:
            return float(self.per_km_table[key])

        # Fallback to mean of speed bins if available
        if key in self.speed_tables and self.speed_tables[key]:
            bins = self.speed_tables[key]
            return float(sum(b.ef_g_per_km for b in bins) / len(bins))

        raise KeyError(f"No per-km factor for {key} and no speed bins available")

    def by_speed(
        self, vehicle_type: str, fuel: str, scope: str, speed_kmh: float
    ) -> float:
        """
        Returns grams CO2e per km using speed-binned factors.
        If the speed falls outside bins, returns the nearest bin’s factor.
        """
        key = self._norm_key(vehicle_type, fuel, scope)
        bins = self.speed_tables.get(key, [])
        if not bins:
            # No bins: fall back to per-km
            return self.per_km(vehicle_type, fuel, scope)

        for b in bins:
            if b.min_kmh <= speed_kmh < b.max_kmh:
                return float(b.ef_g_per_km)

        # Out of range: pick nearest by distance to bin center
        def center(bb: SpeedBin) -> float:
            return (bb.min_kmh + bb.max_kmh) / 2.0

        nearest = min(bins, key=lambda bb: abs(center(bb) - speed_kmh))
        return float(nearest.ef_g_per_km)

    # ---------- Loaders ----------
    @classmethod
    def from_xlsx_defra_2025(
        cls,
        xlsx_path: str | Path,
        *,
        name: str = "defra_2025",
        scope_candidates: Tuple[str, ...] = ("TTW", "WTW"),
    ) -> "GHGFactors":
        """
        Best-effort loader for DEFRA 2025 workbooks.
        We try to discover:
          - Per-km tables (kgCO2e/km or gCO2e/km)
          - Speed-binned tables (km/h ranges)
        This is heuristic because the official workbook layout can change.
        If we can't parse, we raise with a helpful message.
        """
        if pd is None:
            raise RuntimeError(
                "pandas is required to read DEFRA XLSX. Install with: pip install pandas openpyxl"
            )

        xlsx_path = Path(xlsx_path)
        if not xlsx_path.exists():
            raise FileNotFoundError(f"DEFRA factors not found: {xlsx_path}")

        xls = pd.ExcelFile(xlsx_path)  # type: ignore

        per_km_table: Dict[Key, float] = {}
        speed_tables: Dict[Key, List[SpeedBin]] = {}

        # Utilities to guess columns
        def _col(df, *cands: str) -> Optional[str]:
            cols = {c.lower(): c for c in df.columns}
            for c in cands:
                if c in cols:
                    return cols[c]
            # try contains
            for want in cands:
                for lc, orig in cols.items():
                    if want in lc:
                        return orig
            return None

        # Try all sheets and heuristically pick rows with per-km info or speed-bins
        for sheet in xls.sheet_names:
            try:
                df = pd.read_excel(xls, sheet_name=sheet)  # type: ignore
            except Exception:
                continue
            if df is None or df.empty:
                continue

            # Normalize column names to strings
            df.columns = [str(c) for c in df.columns]

            # Guess semantic columns
            veh_col = _col(df, "vehicle type", "vehicle", "vehicle_category", "mode")
            fuel_col = _col(df, "fuel", "powertrain", "technology")
            scope_col = _col(df, "scope", "ttw/wtw", "well-to-wheel", "tank-to-wheel")

            # Emission factor columns (per km)
            ef_gkm_col = _col(df, "gco2e/km", "g/km", "grams co2e per km", "g per km")
            ef_kgkm_col = _col(df, "kgco2e/km", "kg/km", "kg co2e per km")

            # Speed-bins: detect min/max speed & factor per km
            speed_min_col = _col(
                df, "speed min", "min speed", "from", "lower bound (km/h)"
            )
            speed_max_col = _col(
                df, "speed max", "max speed", "to", "upper bound (km/h)"
            )
            ef_speed_gkm_col = _col(
                df, "gco2e/km", "g/km", "grams co2e per km"
            )  # reuse ef if same col

            # Skip if we can't even identify vehicle/fuel columns
            if not veh_col or not fuel_col:
                continue

            # 1) Try per-km rows
            if ef_gkm_col or ef_kgkm_col:
                for _, row in df.iterrows():
                    v = row.get(veh_col)
                    f = row.get(fuel_col)

                    if pd.isna(v) or pd.isna(f):
                        continue

                    # Try to find scope; default to TTW if absent
                    raw_scope = row.get(scope_col) if scope_col else None
                    scope = (
                        str(raw_scope).strip().upper()
                        if raw_scope and not pd.isna(raw_scope)
                        else "TTW"
                    )
                    if scope not in scope_candidates:
                        # If scope value looks like "Well-to-wheel", normalize to WTW; else TTW
                        if "WELL" in scope or "WTW" in scope:
                            scope = "WTW"
                        else:
                            scope = "TTW"

                    # Parse EF
                    ef: Optional[float] = None
                    if ef_gkm_col and not pd.isna(row.get(ef_gkm_col)):
                        ef = float(row.get(ef_gkm_col))
                    elif ef_kgkm_col and not pd.isna(row.get(ef_kgkm_col)):
                        ef = float(row.get(ef_kgkm_col)) * 1000.0  # kg/km -> g/km

                    if ef is None:
                        continue

                    key = cls._norm_key(str(v), str(f), scope)
                    # Keep the smallest EF if duplicates (very rough heuristic)
                    if key not in per_km_table:
                        per_km_table[key] = ef
                    else:
                        per_km_table[key] = min(per_km_table[key], ef)

            # 2) Try speed-binned rows
            if (
                speed_min_col
                and speed_max_col
                and (ef_speed_gkm_col or ef_gkm_col or ef_kgkm_col)
            ):
                # choose an EF column preference
                ef_col = ef_speed_gkm_col or ef_gkm_col or ef_kgkm_col
                for _, row in df.iterrows():
                    v = row.get(veh_col)
                    f = row.get(fuel_col)
                    smin = row.get(speed_min_col)
                    smax = row.get(speed_max_col)
                    efv = row.get(ef_col) if ef_col else None
                    if any(pd.isna(x) for x in (v, f, smin, smax, efv)):
                        continue

                    # scope normalize
                    raw_scope = row.get(scope_col) if scope_col else None
                    scope = (
                        str(raw_scope).strip().upper()
                        if raw_scope and not pd.isna(raw_scope)
                        else "TTW"
                    )
                    if scope not in scope_candidates:
                        if "WELL" in scope or "WTW" in scope:
                            scope = "WTW"
                        else:
                            scope = "TTW"

                    # unit normalize
                    ef_val = float(efv)
                    if ef_col == ef_kgkm_col:
                        ef_val *= 1000.0

                    key = cls._norm_key(str(v), str(f), scope)
                    speed_tables.setdefault(key, []).append(
                        SpeedBin(
                            min_kmh=float(smin),
                            max_kmh=float(smax),
                            ef_g_per_km=float(ef_val),
                        )
                    )

        if not per_km_table and not speed_tables:
            raise RuntimeError(
                f"Could not parse any factors from {xlsx_path}. "
                "If this is the official DEFRA workbook, please export the relevant tables "
                "(road transport per-km and speed-binned factors) to simple sheets with clear headers, "
                "or provide a small curated XLSX."
            )

        # Sort bins
        for k, bins in speed_tables.items():
            bins.sort(key=lambda b: (b.min_kmh, b.max_kmh))

        return cls(per_km_table=per_km_table, speed_tables=speed_tables, name=name)

    @classmethod
    def sample_defra_like(cls, name: str = "sample_defra_2025") -> "GHGFactors":
        """
        Fallback minimal set so you can test end-to-end immediately.
        Values are illustrative only — replace with real DEFRA numbers via XLSX loader above.
        All factors are grams CO2e / km.
        """
        per_km = {
            cls._norm_key("car", "petrol", "TTW"): 180.0,
            cls._norm_key("car", "diesel", "TTW"): 150.0,
            cls._norm_key("van", "diesel", "TTW"): 220.0,
            cls._norm_key("hgv", "diesel", "TTW"): 650.0,
            cls._norm_key("car", "petrol", "WTW"): 220.0,
            cls._norm_key("car", "diesel", "WTW"): 200.0,
        }

        speed = {
            cls._norm_key("car", "petrol", "TTW"): [
                SpeedBin(0, 10, 250.0),
                SpeedBin(10, 30, 190.0),
                SpeedBin(30, 50, 160.0),
                SpeedBin(50, 130, 150.0),
            ],
            cls._norm_key("car", "diesel", "TTW"): [
                SpeedBin(0, 10, 230.0),
                SpeedBin(10, 30, 170.0),
                SpeedBin(30, 50, 140.0),
                SpeedBin(50, 130, 135.0),
            ],
        }
        return cls(per_km_table=per_km, speed_tables=speed, name=name)
