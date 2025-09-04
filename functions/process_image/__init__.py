import json
import logging
import os
import mimetypes
from typing import Optional

import azure.functions as func
import requests
from azure.storage.blob import BlobServiceClient, ContentSettings

try:
    from pymongo import MongoClient
except Exception:
    MongoClient = None

try:
    from bson import ObjectId  # type: ignore
except Exception:
    ObjectId = None  # facultatif

# ---------- Logger ----------
logger = logging.getLogger("process_image")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(name)s] %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# ---------- Config ----------
RAW_CONT = os.getenv("AZURE_BLOB_CONTAINER_RAW", "raw") or "raw"
PROC_CONT = os.getenv("AZURE_BLOB_CONTAINER_PROCESSED", "processed") or "processed"

BLUR_URL = (os.getenv("IA_BLUR_URL") or "").strip()
PREDICT_URL = (os.getenv("IA_PREDICT_URL") or "").strip()
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT_SECONDS", "20"))

def _blob_client() -> BlobServiceClient:
    cs = os.getenv("AzureWebJobsStorage") or os.getenv("StorageConn")
    if not cs:
        raise RuntimeError("AzureWebJobsStorage/StorageConn missing")
    return BlobServiceClient.from_connection_string(cs)

def _mongo():
    uri = os.getenv("MONGO_URI")
    dbn = os.getenv("DB_NAME", "turbodex")
    if not uri or MongoClient is None:
        logger.info("Mongo disabled (no URI or pymongo missing)")
        return None, None
    try:
        cli = MongoClient(uri, serverSelectionTimeoutMS=3000)
        cli.admin.command("ping")
        return cli, cli[dbn]
    except Exception as e:
        logger.warning("Mongo unreachable: %s", e)
        return None, None

def _http_post_image(url: str, field_name: str, filename: str, content: bytes,
                     mime: Optional[str] = None, accept: Optional[str] = None):
    mime = mime or (mimetypes.guess_type(filename)[0] or "application/octet-stream")
    files = {field_name: (filename, content, mime)}
    headers = {}
    if accept:
        headers["Accept"] = accept
    r = requests.post(url, files=files, timeout=HTTP_TIMEOUT, headers=headers)
    try:
        r.raise_for_status()
    except Exception:
        logger.error("HTTP POST %s -> %s %s", url, r.status_code, (r.text or "")[:500])
        raise
    return r

def _safe_json_loads(s: str) -> Optional[dict]:
    try:
        return json.loads(s)
    except Exception as e:
        logger.error("JSON parse error: %s / payload head=%r", e, s[:200])
        return None

# ---------- Main ----------
def main(msg: func.QueueMessage) -> None:
    # Ne jamais lever non-catché : on catch tout à ce niveau
    try:
        # 0) Lire le message
        try:
            raw = msg.get_body().decode("utf-8", errors="replace")
        except Exception as e:
            logger.error("get_body decode error: %s", e)
            return

        logger.info("got queue message (len=%d)", len(raw))
        data = _safe_json_loads(raw)
        if not data:
            return

        post_id = data.get("post_id")
        blob_name = data.get("blob_name")
        if not blob_name:
            logger.error("missing blob_name in message")
            return
        logger.info("parsed post_id=%s blob_name=%s", post_id, blob_name)

        # 1) Télécharger RAW
        try:
            bsc = _blob_client()
            raw_blob = bsc.get_blob_client(container=RAW_CONT, blob=blob_name)
            raw_bytes = raw_blob.download_blob().readall()
            logger.info("downloaded raw bytes=%d", len(raw_bytes))
        except Exception as e:
            logger.exception("failed to download raw: %s", e)
            return

        processed_bytes = raw_bytes
        blur_mime: Optional[str] = None
        tags_payload: Optional[dict] = None

        # 2) Blur (optionnel)
        if BLUR_URL:
            try:
                r = _http_post_image(
                    url=BLUR_URL,
                    field_name="file",
                    filename=os.path.basename(blob_name) or "image.jpg",
                    content=raw_bytes,
                    mime="image/jpeg",
                    accept="image/png",
                )
                processed_bytes = r.content
                blur_mime = r.headers.get("Content-Type") or "image/png"
                logger.info("blur ok bytes=%d mime=%s", len(processed_bytes), blur_mime)
            except Exception as e:
                logger.warning("blur failed, keep raw: %s", e)

        # 3) Predict (optionnel)
        if PREDICT_URL:
            try:
                predict_url = PREDICT_URL if PREDICT_URL.endswith("/") else PREDICT_URL + "/"
                predict_mime = blur_mime or "image/jpeg"
                r = requests.post(
                    predict_url,
                    files={"file": (os.path.basename(blob_name) or "image.png", processed_bytes, predict_mime)},
                    timeout=HTTP_TIMEOUT,
                )
                try:
                    r.raise_for_status()
                except Exception:
                    logger.error("predict HTTP %s: %s", r.status_code, (r.text or "")[:500])
                    raise
                tags_payload = r.json()
                vehicle = None
                rarity = None
                try:
                    if isinstance(tags_payload, dict):
                        v = tags_payload.get("vehicle") or {}
                        mk = (v.get("make") or v.get("brand") or "Unknown")
                        md = (v.get("model") or "Unknown")
                        vehicle = {"make": mk, "model": md}
                        rarity = tags_payload.get("rarity")
                except Exception:
                    pass
                if isinstance(tags_payload, dict):
                    logger.info("predict ok keys=%s", list(tags_payload.keys()))
                else:
                    logger.info("predict ok type=%s", type(tags_payload))
            except Exception as e:
                logger.warning("predict failed: %s", e)
                tags_payload = None

        # 4) Upload PROCESSED
        try:
            proc_blob = bsc.get_blob_client(container=PROC_CONT, blob=blob_name)
            content_type = blur_mime or "image/jpeg"
            proc_blob.upload_blob(
                processed_bytes,
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type),
            )
            logger.info("uploaded processed %s/%s (ct=%s)", PROC_CONT, blob_name, content_type)
        except Exception as e:
            logger.exception("failed to upload processed: %s", e)
            return

        # 5) Update Mongo (post + turbodex)
        cli, db = _mongo()
        if db is not None and post_id and isinstance(post_id, str) and len(post_id) == 24 and (ObjectId is not None):
            try:
                post = db.posts.find_one({"_id": ObjectId(post_id)}, {"_id": 1, "user_id": 1})
                if not post:
                    logger.warning("mongo: post not found, id=%s", post_id)
                else:
                    url = proc_blob.url

                    vehicle = {"make": "Unknown", "model": "Unknown"}
                    rarity = "common"
                    vehicle_key = None
                    if isinstance(tags_payload, dict):
                        make = (tags_payload.get("vehicle_make") or tags_payload.get("make") or "").strip() or "Unknown"
                        model = (tags_payload.get("vehicle_model") or tags_payload.get("model") or "").strip() or "Unknown"
                        rarity = (tags_payload.get("rarity") or "common").lower()
                        vehicle = {"make": make, "model": model}
                        vehicle_key = f"{make}::{model}".lower()

                    update_doc = {
                        "status": "processed",
                        "processed_blob_url": url,
                        "processed_at": __import__("datetime").datetime.utcnow()
                    }
                    if vehicle: update_doc["vehicle"] = vehicle
                    if rarity:  update_doc["rarity"]  = rarity
                    if isinstance(tags_payload, dict):
                        update_doc["ai"] = {
                            "raw": tags_payload,
                            "tags": tags_payload.get("tags")
                        }
                    db.posts.update_one({"_id": ObjectId(post_id)}, {"$set": update_doc})

                    if vehicle_key:
                        user_id = post["user_id"]
                        db.turbodex.update_one(
                            {"user_id": user_id, "vehicle_key": vehicle_key},
                            {
                                "$setOnInsert": {
                                    "first_post_id": ObjectId(post_id),
                                    "captured_at": __import__("datetime").datetime.utcnow(),
                                },
                                "$set": {
                                    "make": vehicle.get("make"),
                                    "model": vehicle.get("model"),
                                    "last_post_id": ObjectId(post_id),
                                    "last_captured_at": __import__("datetime").datetime.utcnow(),
                                },
                            },
                            upsert=True,
                        )
                    logger.info("mongo updated post_id=%s; turbodex upsert=%s", post_id, bool(vehicle_key))
            except Exception as e:
                logger.warning("mongo update skipped: %s", e)

        logger.info("done.")
    except Exception as e:
        logger.exception("FATAL (caught): %s", e)
