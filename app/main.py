from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .routers import health
from .deps import get_db
from .utils.mongo_indexes import ensure_indexes
from .routers import auth

app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION
)

# CORS dev: large pour démarrer (resserrer plus tard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET","POST","DELETE","PATCH","OPTIONS"],
    allow_headers=["*"],
)

# Routes
app.include_router(health.router, prefix="/v1/health", tags=["health"])
app.include_router(auth.router, prefix="/v1/auth", tags=["auth"])

# Optionnel: hooks
@app.on_event("startup")
async def on_startup():
    print(f"[Startup] env={settings.APP_ENV}, version={settings.API_VERSION}")
    await ensure_indexes(get_db())
