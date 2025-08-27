from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from bson import ObjectId
from azure.storage.queue import QueueClient

from ..deps import get_db
from ..deps_auth import get_current_user_id
from ..models.post import PostCreate
from ..config import settings
from ..services.storage_service import public_url

router = APIRouter()

QUEUE_NAME = "process-image"  # assure-toi que la queue existe dans le Storage Account

def enqueue_process(post_id: str, blob_name: str) -> None:
    qc = QueueClient.from_connection_string(
        settings.AZURE_STORAGE_CONNECTION_STRING, queue_name=QUEUE_NAME
    )
    import json
    qc.send_message(json.dumps({"post_id": post_id, "blob_name": blob_name}))

@router.post("")
async def create_post(body: PostCreate, db=Depends(get_db), user_id: str = Depends(get_current_user_id)):
    if not body.blob_name or "/" not in body.blob_name:
        raise HTTPException(400, "bad_blob_name")

    raw_url = public_url(settings.AZURE_BLOB_CONTAINER_RAW, body.blob_name)

    doc = {
        "user_id": ObjectId(user_id),
        "vehicle_id": None,
        "status": "pending",
        "raw_blob_url": raw_url,
        "processed_blob_url": None,
        "city": None, "country": None,
        "taken_at": body.taken_at,
        "likes": [], "reports": [],
        "created_at": datetime.utcnow(),
    }
    res = await db.posts.insert_one(doc)
    post_id = str(res.inserted_id)

    enqueue_process(post_id, body.blob_name)
    return {"id": post_id, "status": "pending"}
