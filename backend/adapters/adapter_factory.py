# adapters/adapter_factory.py
from core.adapter_factory_registry import AdapterFactoryRegistry
from core.interfaces import DistanceMatrixAdapter


def create_adapter(name: str) -> DistanceMatrixAdapter:
    return AdapterFactoryRegistry.get(name)
