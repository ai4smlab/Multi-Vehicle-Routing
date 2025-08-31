# core/load_plugins.py
def load_plugins():
    # Adapters
    from core.register_adapters import register_adapters

    register_adapters()

    # Solvers
    from services.solver_factory import register_solvers, list_solvers

    register_solvers()

    # Optional: log
    from core.adapter_factory_registry import AdapterFactoryRegistry

    AdapterFactoryRegistry.list_adapters()
    list_solvers()
