# core/register_adapters.py
from __future__ import annotations
import os
from typing import Any, Callable

from core.adapter_factory_registry import AdapterFactoryRegistry

# Offline adapters
from adapters.offline.haversine_adapter import HaversineAdapter
from adapters.online.osm_graph_adapter import OsmGraphAdapter
from adapters.offline.euclidean_adapter import EuclideanAdapter

# Online adapters
from adapters.online.openrouteservice_adapter import ORSDistanceMatrixAdapter
from adapters.online.google_matrix_adapter import GoogleMatrixAdapter
from adapters.online.mapbox_matrix_adapter import MapboxMatrixAdapter

try:
    from adapters.online.google_routes_adapter import GoogleRoutesAdapter  # optional
except Exception:
    GoogleRoutesAdapter = None  # type: ignore

_registered = False


def _load_settings() -> Any | None:
    """
    Try several config.py shapes in this order:
      1) get_settings() -> instance
      2) settings       -> instance
      3) Settings()     -> instance
      4) Settings       -> object with attributes (legacy static)
    Return None if none are available.
    """
    try:
        from config import get_settings  # type: ignore

        return get_settings()
    except Exception:
        pass
    try:
        from config import settings  # type: ignore

        return settings
    except Exception:
        pass
    try:
        from config import Settings  # type: ignore

        try:
            return Settings()  # pydantic BaseSettings
        except Exception:
            return Settings  # legacy static container
    except Exception:
        return None


def _get_key(settings_obj: Any, attr_name: str, *env_fallbacks: str) -> str | None:
    """Pull API key from settings object if present; otherwise from env."""
    if settings_obj is not None and hasattr(settings_obj, attr_name):
        val = getattr(settings_obj, attr_name)
        if val:
            return str(val)
    for env in env_fallbacks:
        val = os.getenv(env)
        if val:
            return val
    return None


def _safe_register(name: str, factory: Callable[[], object]) -> None:
    """Don't blow up if already registered (idempotent)."""
    try:
        AdapterFactoryRegistry.register(name, factory)
    except Exception:
        # If your registry raises on duplicates, we just ignore
        pass


def register_adapters() -> None:
    global _registered
    if _registered:
        return

    settings_obj = _load_settings()

    # -----------------------------
    # Offline / local adapters
    # -----------------------------
    # Debug-only Haversine
    if os.getenv("ENABLE_HAVERSINE", "0") == "1":
        _safe_register("haversine", lambda: HaversineAdapter())

    # OSM graph (local routing) — on by default
    if os.getenv("ENABLE_OSM_GRAPH", "1") != "0":
        # buffer (m) and network type are tunable by env
        buffer_m = int(os.getenv("OSM_GRAPH_BUFFER_M", "3000"))
        network_type = os.getenv("OSM_GRAPH_NET", "drive")
        _safe_register(
            "osm_graph",
            lambda: OsmGraphAdapter(buffer_m=buffer_m, network_type=network_type),
        )

        # Euclidean Adapter
        _safe_register("euclidean", lambda: EuclideanAdapter())
    # -----------------------------
    # Online providers
    # -----------------------------
    mapbox_key = _get_key(settings_obj, "MAPBOX_TOKEN", "MAPBOX_TOKEN")
    if mapbox_key:
        _safe_register("mapbox", lambda k=mapbox_key: MapboxMatrixAdapter(api_key=k))

    ors_key = _get_key(
        settings_obj, "ORS_API_KEY", "ORS_API_KEY", "OPENROUTESERVICE_API_KEY"
    )
    if ors_key:
        _safe_register(
            "openrouteservice", lambda k=ors_key: ORSDistanceMatrixAdapter(api_key=k)
        )

    google_key = _get_key(settings_obj, "GOOGLE_API_KEY", "GOOGLE_API_KEY")
    if google_key:
        _safe_register("google", lambda k=google_key: GoogleMatrixAdapter(api_key=k))

    if GoogleRoutesAdapter is not None:
        google_routes_key = _get_key(
            settings_obj, "GOOGLE_ROUTES_API_KEY", "GOOGLE_ROUTES_API_KEY"
        )
        if google_routes_key:
            _safe_register(
                "google_routes",
                lambda k=google_routes_key: GoogleRoutesAdapter(api_key=k),
            )

    _registered = True
