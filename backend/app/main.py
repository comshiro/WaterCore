from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.risk import router as risk_router
from backend.app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.app_debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(risk_router, prefix="/api/v1")


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "WaterCore - weilding Copernicus API is running"}
