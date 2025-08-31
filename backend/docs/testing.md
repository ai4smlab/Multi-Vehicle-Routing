# Testing

Run all:
```bash
pytest -q
```

Selected tests:
```bash
pytest -k solomon_instance_vs_solution -q
RUN_PYOMO_BENCH=1 pytest -k solomon_instance_vs_solution_pyomo -q
RUN_VROOM_BENCH=1 pytest -k solomon_instance_vs_solution_vroom -q
```

Conventions:
- Tests use **self-contained** fixtures or patch dataset roots with `monkeypatch` for determinism.
- For loaders, we prefer **tiny inline files** written to `tmp_path`.
- For solver E2E, we keep a **loose tolerance** vs. benchmark solutions.

Markers:
- `@pytest.mark.slow` for real solver runs.