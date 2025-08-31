# services/emissions/emissions_factory.py
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Literal

from .factors import GHGFactors

# You already placed the workbooks here:
#   services/emissions/presets/ghg-conversion-factors-2025-condensed-set.xlsx
#   services/emissions/presets/ghg-conversion-factors-2025-full-set.xlsx
PRESETS_DIR = Path(__file__).parent / "presets"

PresetName = Literal[
    "defra_2025_full",
    "defra_2025_condensed",
    "defra_2025_sample",
]


@lru_cache(maxsize=8)
def get_factors(preset: PresetName = "defra_2025_condensed") -> GHGFactors:
    """
    Return a cached factors object.
    - 'defra_2025_full'      -> tries to parse the full XLSX
    - 'defra_2025_condensed' -> tries to parse the condensed XLSX
    - 'defra_2025_sample'    -> built-in small sample (for immediate testing)
    """
    if preset == "defra_2025_full":
        xlsx = PRESETS_DIR / "ghg-conversion-factors-2025-full-set.xlsx"
        try:
            return GHGFactors.from_xlsx_defra_2025(xlsx, name="defra_2025_full")
        except Exception as e:
            # Fallback so the backend still runs
            print(
                f"[emissions] WARNING: Failed to parse full DEFRA file: {e}. Using sample factors."
            )
            return GHGFactors.sample_defra_like("defra_2025_sample")

    if preset == "defra_2025_condensed":
        xlsx = PRESETS_DIR / "ghg-conversion-factors-2025-condensed-set.xlsx"
        try:
            return GHGFactors.from_xlsx_defra_2025(xlsx, name="defra_2025_condensed")
        except Exception as e:
            print(
                f"[emissions] WARNING: Failed to parse condensed DEFRA file: {e}. Using sample factors."
            )
            return GHGFactors.sample_defra_like("defra_2025_sample")

    # Default: sample
    return GHGFactors.sample_defra_like("defra_2025_sample")
