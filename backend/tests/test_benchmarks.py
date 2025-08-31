import os
import pytest

# We rely on the existing TestClient "client" fixture from your conftest.
# If you don't have it, uncomment the local client fixture at the bottom.


@pytest.fixture
def tmp_datasets(tmp_path, monkeypatch):
    """
    Create a tiny fake benchmark tree:
      data/
        solomon/
          C101.vrp, C101.sol, R101.vrp
        Vrp-Set-XML100/
          XML100_3375_23.vrp, XML100_3375_23.sol, XML100_0001_01.vrp
    Then point dataset_indexer to this directory and restrict includes.
    """
    base = tmp_path / "data"
    solomon = base / "solomon"
    xml100 = base / "Vrp-Set-XML100"
    solomon.mkdir(parents=True)
    xml100.mkdir(parents=True)

    # Solomon
    (solomon / "C101.vrp").write_text("dummy", encoding="utf-8")
    (solomon / "C101.sol").write_text("solution", encoding="utf-8")
    (solomon / "R101.vrp").write_text("dummy", encoding="utf-8")

    # XML100
    (xml100 / "XML100_3375_23.vrp").write_text("dummy", encoding="utf-8")
    (xml100 / "XML100_3375_23.sol").write_text("solution", encoding="utf-8")
    (xml100 / "XML100_0001_01.vrp").write_text("dummy", encoding="utf-8")

    # Monkeypatch dataset_indexer config to point to our temp tree
    import file_handler.dataset_indexer as di

    monkeypatch.setattr(di, "DATA_DIR", str(base), raising=False)
    # Keep the list tight so unrelated folders don’t show up
    monkeypatch.setattr(
        di, "BENCHMARK_INCLUDE_FOLDERS", {"solomon", "vrp-set-xml100"}, raising=False
    )
    monkeypatch.setattr(di, "BENCHMARK_EXCLUDE_FOLDERS", set(), raising=False)

    # Some versions read from Settings; patch that too if present
    try:
        DATA_DIR = os.getenv("DATA_DIR", "./backend/data")
    except Exception:
        pass

    # Clear any in-memory caches the indexer may hold
    if hasattr(di, "DatasetIndexCache"):
        cache = di.DatasetIndexCache
        if hasattr(cache, "_cache"):
            cache._cache.clear()  # pragma: no cover

    return base


def test_list_benchmarks(client):
    r = client.get("/benchmarks")
    assert r.status_code == 200, r.text
    data = r.json()
    names = [d["name"] for d in data.get("datasets", data)]  # support either shape
    assert "solomon" in names or "Solomon" in names
    assert "Vrp-Set-XML100" in names


def test_list_files_solomon(client):
    r = client.get(
        "/benchmarks/files", params={"dataset": "Solomon", "limit": 50, "offset": 0}
    )
    assert r.status_code == 200, r.text
    items = r.json().get("items") or r.json()
    filenames = [it["name"] for it in items]
    assert "C101.vrp" in filenames
    assert "R101.vrp" in filenames

    # ensure pairing info is present for C101
    c101 = next(it for it in items if it["name"] == "C101.vrp")
    # accept either explicit `solution` field or generic `pair` dict
    assert any(k in c101 for k in ("solution", "pair", "solution_path"))


def test_find_xml_pair(client):
    r = client.get(
        "/benchmarks/find",
        params={"dataset": "Vrp-Set-XML100", "name": "XML100_3375_23"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    # accept either flat or nested shape
    inst = data.get("instance") or data.get("data", {}).get("instance")
    sol = data.get("solution") or data.get("data", {}).get("solution")
    assert inst and inst["name"].endswith(".vrp")
    assert sol and sol["name"].endswith(".sol")


def test_files_search_and_paging(client):
    # search for the tail item by pattern
    r = client.get(
        "/benchmarks/files",
        params={
            "dataset": "Vrp-Set-XML100",
            "q": "3375_23",
            "kind": "instances",
            "limit": 10,
            "offset": 0,
            "sort": "name",
            "order": "asc",
        },
    )
    assert r.status_code == 200, r.text
    items = r.json().get("items") or r.json()
    names = [it["name"] for it in (r.json().get("items") or r.json())]
    assert names == ["XML100_3375_23.vrp"]

    # pagination sanity
    r2 = client.get(
        "/benchmarks/files",
        params={"dataset": "Vrp-Set-XML100", "limit": 1, "offset": 1},
    )
    assert r2.status_code == 200
    items2 = r2.json().get("items") or r2.json()
    assert len(items2) == 1
