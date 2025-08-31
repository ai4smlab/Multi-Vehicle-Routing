# core/adapter_factory_registry.py
from typing import Callable, Dict
from core.interfaces import DistanceMatrixAdapter


class AdapterFactoryRegistry:
    _factories: Dict[str, Callable[[], DistanceMatrixAdapter]] = {}

    @classmethod
    def register(cls, name: str, factory: Callable[[], DistanceMatrixAdapter]) -> None:
        key = name.lower().strip()
        if key in cls._factories:
            raise ValueError(f"Adapter '{name}' is already registered.")
        cls._factories[key] = factory

    @classmethod
    def get(cls, name: str) -> DistanceMatrixAdapter:
        key = name.lower().strip()
        if key not in cls._factories:
            raise ValueError(f"Adapter '{name}' is not registered.")
        return cls._factories[key]()  # create instance

    @classmethod
    def list_adapters(cls) -> list[str]:
        return sorted(cls._factories.keys())
