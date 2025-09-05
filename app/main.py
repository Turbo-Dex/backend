from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .routers import health, auth, uploads
from .deps import get_db
from .utils.mongo_indexes import ensure_indexes
from app.deps import get_db
from app.utils.mongo_indexes import ensure_indexes
from app.routers import posts as posts_router
from .routers.images import router as images_router

app = FastAPI(title=settings.API_TITLE, version=settings.API_VERSION)

# CORS large en dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health.router,  prefix="/v1/health",  tags=["health"])
app.include_router(auth.router,    prefix="/v1/auth",    tags=["auth"])
app.include_router(uploads.router, prefix="/v1/uploads", tags=["uploads"])
app.include_router(posts_router.router, prefix="/v1/posts", tags=["posts"])
app.include_router(images_router,  prefix="/v1/images",  tags=["images"])
app.include_router(posts_router.router, prefix="/posts", tags=["posts"])  

@app.on_event("startup")
async def on_startup():
    print(f"[Startup] env={settings.APP_ENV}, version={settings.API_VERSION}")
    db = get_db()
    print(f"[Startup] JWT_SECRET len={len(settings.JWT_SECRET)} JWT_REFRESH_SECRET len={len(settings.JWT_REFRESH_SECRET)} "
          f"access_min={settings.JWT_ACCESS_MIN} refresh_days={settings.JWT_REFRESH_DAYS}")
    try:
        await db.command("ping")
        await ensure_indexes(db)
        print("[Startup] Mongo OK, indexes ensured")
    except Exception as e:
        print(f"[Startup][WARN] Mongo unreachable, skipping indexes: {e}")
