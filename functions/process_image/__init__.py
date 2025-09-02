# process_image/__init__.py
import os, json, logging, traceback
import azure.functions as func

# Facultatif: pour les tests, saute Mongo si non dispo
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/turbodex")
DB_NAME   = os.environ.get("DB_NAME", "turbodex")
SKIP_MONGO = os.environ.get("MONGO_URI_SKIP", "1") == "1"  # par défaut ON en local

RAW  = os.environ.get("AZURE_BLOB_CONTAINER_RAW", "raw")
PROC = os.environ.get("AZURE_BLOB_CONTAINER_PROCESSED", "processed")

from azure.storage.blob import BlobServiceClient, ContentSettings
def _bsc():
    cs = os.environ["AzureWebJobsStorage"]
    return BlobServiceClient.from_connection_string(cs)

def _db_or_none():
    if SKIP_MONGO:
        return None
    try:
        from pymongo import MongoClient
        return MongoClient(MONGO_URI)[DB_NAME]
    except Exception:
        logging.warning("[process_image] Mongo unreachable, skip update")
        return None

def main(msg: func.QueueMessage) -> None:
    raw = msg.get_body().decode("utf-8", errors="replace")
    logging.info("[process_image] message=%s", raw)

    # 1) parse json
    try:
        data = json.loads(raw)
        post_id   = data.get("post_id")
        blob_name = data.get("blob_name")
        if not blob_name:
            logging.warning("[process_image] missing blob_name -> ack")
            return
    except Exception as e:
        logging.exception("[process_image] invalid json: %s", e)
        return

    # 2) tentative download du RAW (si absent -> on log et on ACK)
    try:
        bsc = _bsc()
        raw_blob = bsc.get_blob_client(container=RAW, blob=blob_name)
        raw_bytes = raw_blob.download_blob().readall()
        in_ct = (raw_blob.get_blob_properties().content_settings.content_type
                 or "application/octet-stream")
        logging.info("[process_image] downloaded %s (%d bytes, %s)", blob_name, len(raw_bytes), in_ct)
    except Exception as e:
        logging.warning("[process_image] cannot download blob %s: %s\n%s",
                        blob_name, e, traceback.format_exc())
        return  # on ACK quand même pour éviter la poison

    # 3) “traitement” no-op et upload vers processed
    try:
        out_bytes = raw_bytes  # no-op
        out_ct = in_ct if in_ct.startswith("image/") else "image/jpeg"

        proc_blob = bsc.get_blob_client(container=PROC, blob=blob_name)
        proc_blob.upload_blob(out_bytes, overwrite=True,
                              content_settings=ContentSettings(content_type=out_ct))
        logging.info("[process_image] uploaded processed/%s", blob_name)
    except Exception as e:
        logging.warning("[process_image] cannot upload processed blob: %s\n%s",
                        e, traceback.format_exc())
        return

    # 4) update Mongo si disponible (sinon on s’arrête là)
    db = _db_or_none()
    if not db or not post_id:
        logging.info("[process_image] skip mongo update (db=%s, post_id=%s)", bool(db), post_id)
        return

    try:
        from bson import ObjectId
        oid = ObjectId(post_id)  # peut lever InvalidId
        url = f"{_bsc().url.rstrip('/')}/{PROC}/{blob_name}"
        db.posts.update_one({"_id": oid},
                            {"$set": {"status": "processed", "processed_blob_url": url}})
        logging.info("[process_image] mongo updated post=%s -> %s", post_id, url)
    except Exception as e:
        logging.warning("[process_image] mongo update failed: %s\n%s",
                        e, traceback.format_exc())
        # on ACK quand même
