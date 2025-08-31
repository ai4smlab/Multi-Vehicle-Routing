# Architecture & UML

This backend is a modular FastAPI service for VRP (Vehicle Routing Problem) experimentation.

```mermaid
flowchart LR
  A[Client/Frontend] -->|HTTP| B[FastAPI Routers]
  B --> C{Adapters? / Benchmarks? / Solver?}
  C -->|/distance-matrix| D[AdapterFactoryRegistry -> Adapter]
  C -->|/benchmarks/*| E[Dataset Indexers & Loaders]
  C -->|/solver| F[SolverFactory -> Solver]
  F --> G[Routes]
  G --> H[Metrics Enrichment]
  H --> A
```

## Module Map (Key Packages)

- `api/` — REST routes (adapters, solver, datasets, files, emissions, status)
- `core/` — interfaces, registries, plugin loading
- `services/` — concrete solvers & adapters, utilities
- `file_handler/` — benchmark indexers & format loaders
- `models/` — pydantic models (matrix, fleet, waypoints, solver payloads)

## Class Diagram (Core Types)

```mermaid
classDiagram
  direction LR

  class VRPSolver {
    <<interface>>
    +solve(...): Routes
  }

  class OrToolsSolver
  class PyomoSolver
  class VroomSolver
  VRPSolver <|.. OrToolsSolver
  VRPSolver <|.. PyomoSolver
  VRPSolver <|.. VroomSolver

  class SolverFactory {
    +register_solver(name, ctor)
    +get_solver(name) VRPSolver
    +list_solvers() string[]
  }

  class AdapterFactoryRegistry {
    +register(name, factory)
    +get(name) DistanceMatrixAdapter
    +list_adapters() string[]
  }

  class DistanceMatrixAdapter {
    <<interface>>
    +matrix(request) : MatrixResult
  }

  class HaversineAdapter
  class OpenRouteServiceAdapter
  class GoogleAdapter
  DistanceMatrixAdapter <|.. HaversineAdapter
  DistanceMatrixAdapter <|.. OpenRouteServiceAdapter
  DistanceMatrixAdapter <|.. GoogleAdapter

  class MatrixResult {
    +distances: float[][]
    +durations: float[][]?
    +coordinates: float[][]?
  }

  class Vehicle {
    +id: string
    +capacity: int[]
    +start: int?
    +end: int?
    +time_window: int[2]?
  }

  class Routes {
    +status: string
    +message: string?
    +routes: Route[]
  }

  class Route {
    +vehicle_id: string
    +waypoint_ids: string[]
    +total_distance: float?
    +total_duration: int?
  }

  class SolveRequest {
    +solver: string
    +matrix: MatrixResult?
    +fleet: Vehicle[] | Fleet
    +depot_index: int
    +demands: int[]?
    +node_time_windows: int[2][]?
    +node_service_times: int[]?
    +pickup_delivery_pairs: PickupDeliveryPair[]?
    +weights: ObjectiveWeights?
    +waypoints: Waypoint[]?
  }

  SolverFactory --> VRPSolver
  AdapterFactoryRegistry --> DistanceMatrixAdapter
  OrToolsSolver --> MatrixResult
  PyomoSolver --> MatrixResult
  VroomSolver --> MatrixResult
  Routes --> Route
```