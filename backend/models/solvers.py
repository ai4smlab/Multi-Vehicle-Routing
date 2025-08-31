from __future__ import annotations
from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field, field_validator
from models.distance_matrix import MatrixResult  # solver consumes a MatrixResult
from models.fleet import Vehicle, Fleet
from models.waypoints import Waypoint


class PickupDeliveryPair(BaseModel):
    pickup: int  # node index in the matrix
    delivery: int  # node index in the matrix
    quantity: Optional[int] = None  # optional; demands[] controls load


class Route(BaseModel):
    vehicle_id: str
    waypoint_ids: List[str]
    total_distance: Optional[float] = None
    total_duration: Optional[int] = None
    emissions: Optional[float] = None
    metadata: Optional[dict] = None


class Routes(BaseModel):
    status: str = "success"
    message: Optional[str] = None
    routes: List[Route] = Field(default_factory=list)  # avoid shared mutable default


class ObjectiveWeights(BaseModel):
    distance: float = 1.0
    time: float = 0.0
    emissions: float = 0.0
    reliability: float = 0.0


class SolveRequest(BaseModel):
    # For /solver/solve: the matrix must already be computed
    solver: str
    matrix: Optional[MatrixResult] = (
        None  # JSON with {distances, durations} parses to MatrixResult
    )
    fleet: Union[List[Vehicle], Fleet]
    depot_index: int = 0

    # Optional per-node info
    demands: Optional[List[int]] = None
    node_time_windows: Optional[List[Optional[List[int]]]] = None
    node_service_times: Optional[List[int]] = None

    # Pickup & delivery pairs
    pickup_delivery_pairs: Optional[List[PickupDeliveryPair]] = None

    # Objective weights for multi-objective solvers
    weights: Optional[ObjectiveWeights] = None

    # coordinate-mode payload for VROOM
    waypoints: Optional[List[Waypoint]] = None

    # ── Normalizers / compatibility shims ─────────────────────────────────────────
    @field_validator("pickup_delivery_pairs", mode="before")
    @classmethod
    def _normalize_pickup_delivery_pairs(cls, v: Any):
        """
        Accept items as:
          - [pickup, delivery]
          - (pickup, delivery)
          - {"pickup": p, "delivery": d, "quantity"?: q}
          - {"from": p, "to": d}   (alias)
        Normalize to list[PickupDeliveryPair]-compatible dicts.
        """
        if v is None:
            return None

        out: List[dict] = []
        for item in v:
            # list/tuple form
            if isinstance(item, (list, tuple)) and len(item) == 2:
                p, d = item
                out.append({"pickup": int(p), "delivery": int(d)})
                continue

            # dict form
            if isinstance(item, dict):
                if "pickup" in item and "delivery" in item:
                    rec = {
                        "pickup": int(item["pickup"]),
                        "delivery": int(item["delivery"]),
                    }
                    if "quantity" in item and item["quantity"] is not None:
                        rec["quantity"] = int(item["quantity"])
                    out.append(rec)
                    continue
                if "from" in item and "to" in item:
                    out.append(
                        {"pickup": int(item["from"]), "delivery": int(item["to"])}
                    )
                    continue

            raise ValueError(
                "Each pickup_delivery_pairs item must be [pickup, delivery], "
                "(pickup, delivery), or {pickup:int, delivery:int[, quantity:int]} (or {from,to})."
            )
        return out
