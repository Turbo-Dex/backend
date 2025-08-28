import json, os, io, traceback
import azure.functions as func
from azure.storage.blob import BlobServiceClient, ContentSettings
from pymongo import MongoClient
from bson import ObjectId

# ----- Config depuis env -----
AZURE_STORAGE_CS = os.environ["AzureWebJobsStorage"]
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/turbodex")
DB_NAME = os.environ.get("DB_NAME", "turbodex")
RAW = os.environ.get("AZURE_BLOB_CONTAINER_RAW", "raw")
PROC = os.environ.get("AZURE_BLOB_CONTAINER_PROCESSED", "processed")

# ----- Singletons -----
_bsc = None
_db = None

def bsc() -> BlobServiceClient:
    global _bsc
    if _bsc is None:
        _bsc = BlobServiceClient.from_connection_string(AZURE_STORAGE_CS)
    return _bsc

def db():
    global _db
    if _db is None:
        _db = MongoClient(MONGO_URI)[DB_NAME]
    return _db

def public_url(base_url: str, container: str, blob_name: str) -> str:
    return f"{base_url.rstrip('/')}/{container.strip('/')}/{blob_name.lstrip('/')}"

def main(msg: func.QueueMessage) -> None:
    raw = msg.get_body().decode("utf-8")
    print(f"[process_image] message: {raw}")

    try:
        payload = json.loads(raw)
        post_id = payload["post_id"]
        blob_name = payload["blob_name"]
    except Exception as e:
        print(f"[ERROR] bad message: {e}")
        return

    try:
        svc = bsc()

        # 1) Download RAW
        raw_blob = svc.get_blob_client(container=RAW, blob=blob_name)
        raw_bytes = raw_blob.download_blob().readall()
        in_ct = (raw_blob.get_blob_properties().content_settings.content_type
                 or "application/octet-stream")

        # 2) *** Placeholder traitement *** :
        # Ici on fait un simple passthrough (ton collègue IA remplacera).
        out_bytes = raw_bytes
        out_ct = in_ct if in_ct.startswith("image/") else "image/jpeg"

        # 3) Upload PROCESSED (même nom)
        proc_blob = svc.get_blob_client(container=PROC, blob=blob_name)
        proc_blob.upload_blob(
            out_bytes,
            overwrite=True,
            content_settings=ContentSettings(content_type=out_ct),
        )

        # 4) Update Mongo
        dbase = db()
        url = public_url(svc.url, PROC, blob_name)
        res = dbase.posts.update_one(
            {"_id": ObjectId(post_id)},
            {"$set": {
                "status": "processed",
                "processed_blob_url": url,
                "vehicle_id": None
            }}
        )
        if res.matched_count != 1:
            print(f"[WARN] post not found: {post_id}")
        else:
            print(f"[OK] post={post_id} processed -> {url}")

    except Exception as e:
        print(f"[ERROR] processing failed: {e}")
        traceback.print_exc()
        try:
            db().posts.update_one(
                {"_id": ObjectId(post_id)},
                {"$set": {"status": "rejected"}}
            )
        except Exception as e2:
            print(f"[ERROR] cannot mark rejected: {e2}")
