# api/emissions_routes.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Literal

from services.emissions.calculator import Leg as LegDC, emissions_for_leg
from services.emissions.emissions_factory import get_factors, PresetName

router = APIRouter(prefix="/emissions", tags=["emissions"])


class LegModel(BaseModel):
    distance_km: float = Field(..., ge=0)
    duration_s: Optional[float] = Field(None, ge=0)
    vehicle_type: str
    fuel: str
    scope: Literal["TTW", "WTW"] = "TTW"

    def to_dc(self) -> LegDC:
        return LegDC(
            distance_km=self.distance_km,
            duration_s=self.duration_s,
            vehicle_type=self.vehicle_type,
            fuel=self.fuel,
            scope=self.scope,
        )


class EmissionsRequest(BaseModel):
    # Use the sample preset by default so tests don’t depend on XLSX parsing
    preset: Optional[PresetName] = "defra_2025_sample"
    legs: List[LegModel]


class EmissionsResponse(BaseModel):
    status: str = "success"
    preset: str
    total_kgco2e: float
    per_leg_kgco2e: List[float]
    units: str = "kgCO2e"


@router.post("/estimate", response_model=EmissionsResponse)
def estimate_emissions(req: EmissionsRequest):
    try:
        factors = get_factors(req.preset or "defra_2025_sample")
        legs_dc = [leg.to_dc() for leg in req.legs]

        per_leg = [emissions_for_leg(leg, factors) for leg in legs_dc]
        total = float(sum(per_leg))

        return EmissionsResponse(
            preset=factors.name,
            total_kgco2e=total,
            per_leg_kgco2e=[float(x) for x in per_leg],
        )
    except Exception as e:
        # 400 rather than 500 because most failures will be bad inputs / unknown factors
        raise HTTPException(status_code=400, detail=f"Emissions estimation failed: {e}")
