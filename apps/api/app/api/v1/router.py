from fastapi import APIRouter

from app.api.v1.routes.games import router as games_router
from app.api.v1.routes.metadata import router as metadata_router
from app.api.v1.routes.models import router as models_router
from app.api.v1.routes.recommendations import router as recommendations_router

router = APIRouter(prefix="/api/v1")
router.include_router(games_router)
router.include_router(metadata_router)
router.include_router(models_router)
router.include_router(recommendations_router)
