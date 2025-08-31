def test_emissions_sample(client):
    payload = {
        "preset": "defra_2025_sample",
        "legs": [
            # Leg 1: 10 km, no duration -> per-km for (car, petrol, TTW) = 180 g/km => 1.8 kg
            {
                "distance_km": 10.0,
                "vehicle_type": "car",
                "fuel": "petrol",
                "scope": "TTW",
            },
            # Leg 2: 5 km in 600s => 30 km/h -> falls into bin [30,50) = 160 g/km => 0.8 kg
            {
                "distance_km": 5.0,
                "duration_s": 600,
                "vehicle_type": "car",
                "fuel": "petrol",
                "scope": "TTW",
            },
        ],
    }
    r = client.post("/emissions/estimate", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["status"] == "success"
    # Allow either name (depends on how your factory labels the sample)
    assert data["preset"] in ("defra_2025_sample", "sample_defra_2025")

    # total should be 1.8 + 0.8 = 2.6 kg
    assert abs(data["total_kgco2e"] - 2.6) < 1e-6
    assert len(data["per_leg_kgco2e"]) == 2
    assert abs(data["per_leg_kgco2e"][0] - 1.8) < 1e-6
    assert abs(data["per_leg_kgco2e"][1] - 0.8) < 1e-6
