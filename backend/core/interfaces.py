from __future__ import annotations
from abc import ABC, abstractmethod
from models.distance_matrix import MatrixRequest, MatrixResult
from models.solvers import SolveRequest, Routes


class DistanceMatrixAdapter(ABC):
    """All online/offline distance matrix providers must implement this."""

    @abstractmethod
    async def get_matrix(self, request: MatrixRequest) -> MatrixResult: ...


class VRPSolver(ABC):
    """All solvers (OR-Tools, VROOM, Pyomo, …) must implement this."""

    @abstractmethod
    def solve(self, request: SolveRequest) -> Routes: ...
