# models/emissions.py
from __future__ import annotations
from typing import Optional, Dict
from pydantic import BaseModel, Field


class EmissionFactors(BaseModel):
    """Default tailpipe+upstream factors (kg CO2e per km). Override as needed."""

    defaults: Dict[str, float] = Field(
        default_factory=lambda: {
            "diesel": 0.27,  # ~270 g/km (example)
            "petrol": 0.25,  # ~250 g/km (example)
            "cng": 0.20,  # example
            "ev": 0.05,  # grid-dependent placeholder
            "unknown": 0.25,
        }
    )

    def factor_for(
        self, fuel: Optional[str], fallback: Optional[float] = None
    ) -> float:
        if fallback is not None:
            return float(fallback)
        key = (fuel or "unknown").lower()
        return float(self.defaults.get(key, self.defaults["unknown"]))


class EmissionsRequest(BaseModel):
    distance_km: float
    fuel_type: Optional[str] = None
    factor_kg_per_km: Optional[float] = None


class EmissionsResult(BaseModel):
    kg_co2e: float
    g_co2e: int
