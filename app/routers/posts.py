# ... imports existants
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from bson import ObjectId
from ..deps import get_db
from ..deps_auth import get_current_user_id
from ..models.post import PostCreate
from ..config import settings
from ..services.storage_service import public_url
from azure.storage.queue import QueueClient
from random import choices
from typing import Optional

router = APIRouter()

QUEUE_NAME = "process-image"

def _user_public(u) -> dict:
    return {
        "id": str(u["_id"]),
        "name": u.get("display_name") or u.get("username") or "Unknown",
        "avatar_url": u.get("avatar_url"),
    }

@router.get("/feed")
async def get_feed(scope: str = "world", limit: int = 20, cursor: Optional[str] = None,
                   user_id: str = Depends(get_current_user_id), db=Depends(get_db)):
    limit = max(1, min(50, limit))
    q = {}
    if cursor:
        q["_id"] = {"$lt": ObjectId(cursor)}
    cur = db.posts.find(q).sort([("created_at",-1), ("_id",-1)]).limit(limit)
    items = []
    async for p in cur:
        img = p.get("processed_blob_url") or p.get("raw_blob_url")
        items.append({
            "id": str(p["_id"]),
            "user": {"id": str(p["user_id"]), "name": "Unknown", "avatar_url": None},
            "image_url": img,
            "rarity": p.get("rarity") or "common",
            "taken_at": (p.get("taken_at") or p.get("created_at")).isoformat() + "Z",
            "city": p.get("city"), "country": p.get("country"),
            "make": (p.get("vehicle") or {}).get("make") or "Unknown",
            "model": (p.get("vehicle") or {}).get("model") or "Unknown",
            "likes_count": len(p.get("likes") or []),
            "liked_by_me": False  # simplifié; ajoute ta logique si besoin
        })
    next_cursor = items[-1]["id"] if len(items) == limit else None
    return {"items": items, "next_cursor": next_cursor}

@router.post("/{post_id}/like")
async def like_post(post_id: str, user_id: str = Depends(get_current_user_id), db=Depends(get_db)):
    await db.posts.update_one({"_id": ObjectId(post_id)}, {"$addToSet": {"likes": ObjectId(user_id)}})
    return {"ok": True}

@router.delete("/{post_id}/like")
async def unlike_post(post_id: str, user_id: str = Depends(get_current_user_id), db=Depends(get_db)):
    await db.posts.update_one({"_id": ObjectId(post_id)}, {"$pull": {"likes": ObjectId(user_id)}})
    return {"ok": True}

@router.post("/{post_id}/report")
async def report_post(post_id: str, body: dict, user_id: str = Depends(get_current_user_id), db=Depends(get_db)):
    reason = (body or {}).get("reason") or "unspecified"
    await db.posts.update_one({"_id": ObjectId(post_id)}, {"$push": {"reports": {
        "user_id": ObjectId(user_id), "reason": reason, "at": datetime.utcnow()
    }}})
    return {"ok": True}

def enqueue_process(post_id: str, blob_name: str) -> None:
    conn = settings.AZURE_STORAGE_CONNECTION_STRING
    q = QueueClient.from_connection_string(conn, queue_name=QUEUE_NAME)
    try:
        q.create_queue()
    except Exception:
        pass
    payload = {"post_id": post_id, "blob_name": blob_name}
    q.send_message(__import__("json").dumps(payload))

@router.post("")
async def create_post(body: PostCreate, user_id: str = Depends(get_current_user_id), db=Depends(get_db)):
    raw_url = public_url(settings.AZURE_BLOB_CONTAINER_RAW, body.blob_name)
    if not raw_url:
        raise HTTPException(400, "bad_blob_name")

    doc = {
        "user_id": ObjectId(user_id),
        "blob_name": body.blob_name,
        "raw_blob_url": raw_url,
        "processed_blob_url": None,
        "status": "pending",
        "taken_at": body.taken_at,
        "gps": body.gps,
        "city": None, "country": None,
        "vehicle": {"make": "Unknown", "model": "Unknown"},
        "rarity": "common",
        "likes": [],
        "reports": [],
        "created_at": datetime.utcnow(),
    }
    res = await db.posts.insert_one(doc)
    post_id = str(res.inserted_id)

    enqueue_process(post_id, body.blob_name)

    # --- capture_result minimal pour l’app ---
    # new_for_user = "premier post de la journée" (ex) ; ici simple heuristique
    today0 = datetime.utcnow().date()
    todays = await db.posts.count_documents({
        "user_id": ObjectId(user_id),
        "created_at": {"$gte": datetime(today0.year, today0.month, today0.day)}
    })
    new_for_user = todays <= 1

    # Petite RNG pour la démo (à remplacer quand votre IA renverra une vraie rareté)
    rarity = choices(["common","rare","epic","legendary"], weights=[85,10,4,1])[0]

    return {
        "id": post_id,
        "status": "pending",
        "capture_result": {
            "new_for_user": bool(new_for_user),
            "rarity": rarity,
            "vehicle_name": "Unknown vehicle",
            "xp_gained": 10 if new_for_user else 2
        }
    }

@router.get("/{post_id}")
async def get_post(post_id: str, user_id: str = Depends(get_current_user_id), db=Depends(get_db)):
    try:
        _id = ObjectId(post_id)
    except Exception:
        raise HTTPException(400, "bad_post_id")
    p = await db.posts.find_one({"_id": _id}, {
        "_id": 1, "status": 1, "processed_blob_url": 1, "vehicle": 1, "rarity": 1
    })
    if not p:
        raise HTTPException(404, "post_not_found")
    return {
        "id": str(_id),
        "status": p.get("status", "pending"),
        "processed_blob_url": p.get("processed_blob_url"),
        "vehicle": p.get("vehicle"),
        "rarity": p.get("rarity", "common")
    }