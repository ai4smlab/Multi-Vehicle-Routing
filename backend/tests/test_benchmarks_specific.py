# backend/tests/test_benchmarks_specific.py
import os
import pytest

XML_DATASET = "Vrp-Set-XML100"
XML_NAME = "XML100_3375_23"
SOLOMON_DATASET = "solomon"
SOLOMON_TARGET = "c101.txt"


@pytest.mark.skipif(
    not os.path.isdir(os.environ.get("DATA_DIR", "backend/data")),
    reason="DATA_DIR not present",
)
def test_vrp_set_xml100_pair(client):
    # Ensure pair lookup finds both .vrp and .sol
    r = client.get(
        "/benchmarks/find", params={"dataset": XML_DATASET, "name": XML_NAME}
    )
    assert r.status_code == 200, r.text
    data = r.json()

    # accept either flat or nested response shape
    instance = data.get("instance") or data.get("data", {}).get("instance")
    solution = data.get("solution") or data.get("data", {}).get("solution")

    assert instance, "Instance not found"
    assert solution, "Solution not found"
    assert instance["name"].endswith(".vrp")
    assert solution["name"].endswith(".sol")

    # Same base name?
    assert (
        os.path.splitext(instance["name"])[0] == os.path.splitext(solution["name"])[0]
    )


@pytest.mark.skipif(
    not os.path.isdir(os.environ.get("DATA_DIR", "backend/data")),
    reason="DATA_DIR not present",
)
def test_solomon_c101_listed(client):
    # Paging/search listing should find c101.txt under the solomon dataset
    r = client.get(
        "/benchmarks/files",
        params={
            "dataset": SOLOMON_DATASET,
            "q": "c101",
            "exts": ".txt",
            "limit": 50,
            "offset": 0,
            "sort": "name",
            "order": "asc",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    items = data.get("items") or data

    names = [it["name"] for it in items]
    assert any(
        n.lower().endswith(SOLOMON_TARGET) for n in names
    ), f"{SOLOMON_TARGET} not listed"
