import os
import logging
from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware

from models import init_db

# Import domain route modules
from routes.auth import router as auth_router
from routes.files import router as files_router
from routes.recipes import router as recipes_router
from routes.batch import router as batch_router
from routes.webhooks import router as webhooks_router
from routes.storage import router as storage_router
from routes.executions import router as executions_router
from routes.samples import router as samples_router
from routes.health import router as health_router
from routes.connectors import router as connectors_router
from routes.schedules import router as schedules_router

logger = logging.getLogger("cleansheet.api")

# Initialize database tables
init_db()

app = FastAPI(title="Anclora CleanSheet API", version="1.0.0")

# Router with /api prefix
api_router = APIRouter(prefix="/api")

# Register domain sub-routers under /api
api_router.include_router(auth_router)
api_router.include_router(files_router)
api_router.include_router(recipes_router)
api_router.include_router(batch_router)
api_router.include_router(webhooks_router)
api_router.include_router(storage_router)
api_router.include_router(executions_router)
api_router.include_router(samples_router)
api_router.include_router(health_router)
api_router.include_router(connectors_router)
api_router.include_router(schedules_router)

# Mount top-level api_router onto FastAPI app
app.include_router(api_router)

# CORS setup: allow explicit origins + wildcard fallback safely
frontend_origin = os.environ.get("FRONTEND_URL", "https://sheet-normalizer.preview.emergentagent.com")
cors_origins = [frontend_origin, "http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://.*\.preview\.emergentagent\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
