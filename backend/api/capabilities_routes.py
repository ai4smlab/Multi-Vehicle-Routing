from fastapi import APIRouter
from core.capabilities import filter_registered
from services.solver_factory import register_solvers, list_solvers
from core.adapter_factory_registry import AdapterFactoryRegistry

router = APIRouter(prefix="/capabilities", tags=["capabilities"])


@router.get("", summary="List solver/adapter capabilities")
def get_capabilities():
    register_solvers()  # idempotent
    registered_solvers = list_solvers()
    registered_adapters = AdapterFactoryRegistry.list_adapters()
    data = filter_registered(registered_solvers, registered_adapters)
    return {"status": "success", "data": data}
