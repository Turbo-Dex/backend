from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .routers import health, auth, uploads
from app.routers import posts
from .deps import get_db
from .utils.mongo_indexes import ensure_indexes

app = FastAPI(title=settings.API_TITLE, version=settings.API_VERSION)

# CORS large en dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET","POST","DELETE","PATCH","OPTIONS"],
    allow_headers=["*"],
)

# Routes
app.include_router(health.router,  prefix="/v1/health",  tags=["health"])
app.include_router(auth.router,    prefix="/v1/auth",    tags=["auth"])
app.include_router(uploads.router, prefix="/v1/uploads", tags=["uploads"])
app.include_router(posts.router,   prefix="/v1/posts",   tags=["posts"])

@app.on_event("startup")
async def on_startup():
    print(f"[Startup] env={settings.APP_ENV}, version={settings.API_VERSION}")
    # tolérer Mongo down en dev pour éviter crash
    db = get_db()
    try:
        await db.command("ping")
        await ensure_indexes(db)
        print("[Startup] Mongo OK, indexes ensured")
    except Exception as e:
        print(f"[Startup][WARN] Mongo unreachable, skipping indexes: {e}")

