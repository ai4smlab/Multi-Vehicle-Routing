from fastapi import APIRouter
from core.adapter_factory_registry import AdapterFactoryRegistry
from services.solver_factory import list_solvers

router = APIRouter(prefix="/status", tags=["status"])


@router.get("/adapters")
def adapters():
    return {"adapters": AdapterFactoryRegistry.list_adapters()}


@router.get("/solvers")
def solvers():
    return {"solvers": list_solvers()}
