# backend/tests/conftest.py
import os
import sys
import pytest
from shutil import which
from fastapi.testclient import TestClient

# Make /Project/backend importable as top-level
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Ensure a non-empty token so capabilities can include mapbox_optimizer (if you rely on it)
os.environ.setdefault("TEST_MAPBOX_TOKEN", "test-token")

# Import app only after setting env
from main import app


def _register_solvers_if_needed():
    """Make sure solver registry is populated for /capabilities-based tests."""
    try:
        from services.solver_factory import register_solvers

        register_solvers()
    except Exception:
        # Pyomo might be missing CBC, etc.—ignore here, tests will skip gracefully.
        pass


@pytest.fixture(scope="session")
def client():
    _register_solvers_if_needed()
    # Use context manager so FastAPI lifespan (startup/shutdown) runs
    with TestClient(app) as c:
        yield c


def solver_available(name: str) -> bool:
    return which(name) is not None


@pytest.fixture(scope="session")
def has_ors():
    return bool(os.getenv("ORS_API_KEY"))


@pytest.fixture(scope="session")
def has_cbc():
    return solver_available("cbc")
