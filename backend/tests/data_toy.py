# tests/data_toy.py

# Distances in KM, durations in SECONDS where provided

TOY_CVRP = {
    "matrix": {
        "distances": [
            [0, 5, 7],
            [5, 0, 3],
            [7, 3, 0],
        ]
    },
    "fleet": [{"id": "veh-1", "capacity": [999], "start": 0, "end": 0}],
    "depot_index": 0,
}

TOY_TW = {
    "matrix": {
        "distances": [
            [0, 5, 7],
            [5, 0, 3],
            [7, 3, 0],
        ],
        "durations": [
            [0, 300, 420],
            [300, 0, 180],
            [420, 180, 0],
        ],
    },
    "fleet": [
        {
            "id": "veh-1",
            "capacity": [10],
            "time_window": [0, 3600],
            "start": 0,
            "end": 0,
        }
    ],
    "depot_index": 0,
    "demands": [0, 4, 4],
    "node_time_windows": [[0, 3600], [0, 3600], [600, 3600]],
    "node_service_times": [0, 120, 120],
}

TOY_PD = {
    "matrix": {
        "distances": [
            [0, 5, 7],
            [5, 0, 3],
            [7, 3, 0],
        ]
    },
    "fleet": [{"id": "veh-1", "capacity": [10], "start": 0, "end": 0}],
    "depot_index": 0,
    "demands": [0, 4, -4],
    "pickup_delivery_pairs": [{"pickup": 1, "delivery": 2}],
}

# For VROOM coordinate-mode test
TOY_VROOM_COORD = {
    "matrix": {
        "distances": [
            [0, 1, 2],
            [1, 0, 1],
            [2, 1, 0],
        ],
        "durations": [
            [0, 600, 1200],
            [600, 0, 600],
            [1200, 600, 0],
        ],
        "coordinates": [
            [-122.4194, 37.7749],
            [-118.2437, 34.0522],
            [-115.1398, 36.1699],
        ],
    },
    "fleet": [{"id": "veh-1", "capacity": [999], "start": 0, "end": 0}],
    "depot_index": 0,
}
