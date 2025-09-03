import json
import logging
import os
import mimetypes
from typing import Optional

import azure.functions as func
import requests
from azure.storage.blob import BlobServiceClient

try:
    from pymongo import MongoClient
except Exception:
    MongoClient = None

try:
    from bson import ObjectId  # type: ignore
except Exception:
    ObjectId = None  # facultatif

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
        logging.info("[process_image] Mongo disabled (no URI or pymongo missing)")
        return None, None
    try:
        cli = MongoClient(uri, serverSelectionTimeoutMS=3000)
        cli.admin.command("ping")
        return cli, cli[dbn]
    except Exception as e:
        logging.warning("[process_image] Mongo unreachable: %s", e)
        return None, None

def _http_post_image(url: str, field_name: str, filename: str, content: bytes, mime: Optional[str] = None, accept: Optional[str] = None):
    if not mime:
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    files = {field_name: (filename, content, mime)}
    headers = {}
    if accept:
        headers["Accept"] = accept
    r = requests.post(url, files=files, timeout=HTTP_TIMEOUT, headers=headers)
    try:
        r.raise_for_status()
    except Exception:
        logging.error("[process_image] HTTP POST %s -> %s %s", url, r.status_code, (r.text or "")[:500])
        raise
    return r

def _safe_json_loads(s: str) -> Optional[dict]:
    try:
        return json.loads(s)
    except Exception as e:
        logging.error("[process_image] JSON parse error: %s / payload head=%r", e, s[:200])
        return None

# ---------- Main ----------
def main(msg: func.QueueMessage) -> None:
    # Never raise out of this function unless it's truly fatal to the host.
    try:
        # 0) Lecture du message
        try:
            raw = msg.get_body().decode("utf-8", errors="replace")
        except Exception as e:
            logging.error("[process_image] get_body decode error: %s", e)
            return

        logging.info("[process_image] got queue message (len=%d)", len(raw))
        data = _safe_json_loads(raw)
        if not data:
            # message corrompu → on termine sans throw (sinon poison)
            return

        post_id = data.get("post_id")
        blob_name = data.get("blob_name")
        if not blob_name:
            logging.error("[process_image] missing blob_name in message")
            return
        logging.info("[process_image] parsed post_id=%s blob_name=%s", post_id, blob_name)

        # 1) Télécharge RAW
        try:
            bsc = _blob_client()
            raw_blob = bsc.get_blob_client(container=RAW_CONT, blob=blob_name)
            raw_bytes = raw_blob.download_blob().readall()
            logging.info("[process_image] downloaded raw bytes=%d", len(raw_bytes))
        except Exception as e:
            logging.exception("[process_image] failed to download raw: %s", e)
            return

        processed_bytes = raw_bytes
        blur_mime = None
        tags_payload = None

        # 2) Blur (optionnel)
        if BLUR_URL:
            try:
                r = _http_post_image(
                    url=BLUR_URL,
                    field_name="file",
                    filename=os.path.basename(blob_name) or "image.jpg",
                    content=raw_bytes,
                    mime="image/jpeg",
                    accept="image/png"
                )
                processed_bytes = r.content
                blur_mime = r.headers.get("Content-Type") or "image/png"
                logging.info("[process_image] blur ok bytes=%d mime=%s", len(processed_bytes), blur_mime)
            except Exception as e:
                logging.warning("[process_image] blur failed, keep raw: %s", e)

        # 3) Predict (optionnel)
        if PREDICT_URL:
            try:
                if not PREDICT_URL.endswith("/"):
                    PREDICT_URL_local = PREDICT_URL + "/"
                else:
                    PREDICT_URL_local = PREDICT_URL

                predict_mime = blur_mime or "image/jpeg"
                r = requests.post(
                    PREDICT_URL_local,
                    files={"file": (os.path.basename(blob_name) or "image.png", processed_bytes, predict_mime)},
                    timeout=HTTP_TIMEOUT,
                )
                try:
                    r.raise_for_status()
                except Exception:
                    logging.error("[process_image] predict HTTP %s: %s", r.status_code, (r.text or "")[:500])
                    raise

                tags_payload = r.json()
                if isinstance(tags_payload, dict):
                    logging.info("[process_image] predict ok keys=%s", list(tags_payload.keys()))
                else:
                    logging.info("[process_image] predict ok type=%s", type(tags_payload))
            except Exception as e:
                logging.warning("[process_image] predict failed: %s", e)
                tags_payload = None

        # 4) Upload PROCESSED
        try:
            proc_blob = bsc.get_blob_client(container=PROC_CONT, blob=blob_name)
            # si blur => souvent PNG ; on met un content_type cohérent
            content_type = "image/png" if blur_mime else "application/octet-stream"
            proc_blob.upload_blob(processed_bytes, overwrite=True, content_type=content_type)
            logging.info("[process_image] uploaded processed %s/%s", PROC_CONT, blob_name)
        except Exception as e:
            logging.exception("[process_image] failed to upload processed: %s", e)
            return

        # 5) Update Mongo (optionnel)
        cli, db = _mongo()
        if (db is not None) and post_id and isinstance(post_id, str) and len(post_id) == 24 and (ObjectId is not None):
            try:
                url = proc_blob.url
                update_doc = {
                    "status": "processed",
                    "processed_blob_url": url,
                    "processed_at": __import__("datetime").datetime.utcnow()
                }
                if isinstance(tags_payload, dict):
                    update_doc["ai"] = {
                        "raw": tags_payload,
                        "tags": tags_payload.get("tags")
                    }

                db.posts.update_one(
                    {"_id": ObjectId(post_id)},
                    {"$set": update_doc}
                )
                logging.info("[process_image] mongo updated post_id=%s", post_id)
            except Exception as e:
                logging.warning("[process_image] mongo update skipped: %s", e)

        logging.info("[process_image] done.")
    except Exception as e:
        # Dernière barrière pour éviter le poison à cause d'une exception non gérée
        logging.exception("[process_image] FATAL (caught): %s", e)

