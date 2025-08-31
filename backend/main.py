from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.adapters_routes import router as adapters_routes
from api.solver_routes import router as solver_router
from api.data_routes import router as osm_router
from api.status import router as status_router
from api.benchmarks_routes import router as benchmarks_router
from api.emissions_routes import router as emissions_router
from api.files_routes import router as files_router
from api.capabilities_routes import router as capabilities_router
from api.mapbox_routes import router as mapbox_router
from api.routes_geometry import router as routes_geometry
from api.health import router as health_router
from core.load_plugins import load_plugins
from contextlib import asynccontextmanager
import os


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_plugins()  # <-- your plugin loading logic
    yield


app = FastAPI(title="VRP Adapter Backend", lifespan=lifespan)

# CORS (adjust for your frontend)
origins = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(adapters_routes)
app.include_router(solver_router)
app.include_router(osm_router)
app.include_router(status_router)
app.include_router(benchmarks_router)
app.include_router(emissions_router)
app.include_router(files_router)
app.include_router(capabilities_router)
app.include_router(mapbox_router)
app.include_router(routes_geometry)
app.include_router(health_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
