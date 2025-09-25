from fastapi import APIRouter

from src.api.v1.admin import admin_router
from src.api.v1.cities import cities_router
from src.api.v1.guardrail import guardrail_router
from src.api.v1.orchestrator import orchestrator_router
from src.api.v1.weather import weather_router

# Create main router
router = APIRouter(prefix="/api/v1")

# Include all sub-routers
router.include_router(admin_router)
router.include_router(cities_router)
router.include_router(guardrail_router)
router.include_router(orchestrator_router)
router.include_router(weather_router)
