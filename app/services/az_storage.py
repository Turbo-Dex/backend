# app/services/az_storage.py
import json
import uuid
from datetime import datetime
from typing import Tuple, Optional

from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.storage.queue import QueueClient
from azure.storage.queue._message_encoding import (
    TextBase64EncodePolicy, TextBase64DecodePolicy
)

from app.config import settings

# --- Clients singletons -------------------------------------------------------
_blob_service_client: Optional[BlobServiceClient] = None
_queue_client: Optional[QueueClient] = None

def get_blob_service() -> BlobServiceClient:
    global _blob_service_client
    if _blob_service_client is None:
        _blob_service_client = BlobServiceClient.from_connection_string(
            settings.AZURE_STORAGE_CONN
        )
    return _blob_service_client

def get_queue_client() -> QueueClient:
    global _queue_client
    if _queue_client is None:
        _queue_client = QueueClient.from_connection_string(
            settings.AZURE_STORAGE_CONN,
            queue_name=settings.AZURE_QUEUE_NAME,
            message_encode_policy=TextBase64EncodePolicy(),
            message_decode_policy=TextBase64DecodePolicy(),
        )
        # s’assure que la queue existe (idempotent)
        _queue_client.create_queue(exist_ok=True)
    return _queue_client

# --- Helpers ------------------------------------------------------------------
def build_blob_name(original_filename: str) -> str:
    # 20250902/uuid4.ext
    ext = ""
    if "." in (original_filename or ""):
        ext = "." + original_filename.rsplit(".", 1)[1].lower()
    date_prefix = datetime.utcnow().strftime("%Y%m%d")
    return f"{date_prefix}/{uuid.uuid4().hex}{ext}"

def upload_raw_bytes(blob_name: str, data: bytes, content_type: str) -> str:
    """
    Upload dans le conteneur RAW. Retourne l'URL du blob.
    """
    bsc = get_blob_service()
    blob = bsc.get_blob_client(
        container=settings.AZURE_BLOB_CONTAINER_RAW,
        blob=blob_name
    )
    blob.upload_blob(
        data,
        overwrite=True,
        content_settings=ContentSettings(content_type=content_type)
    )
    return blob.url

def enqueue_process_image(post_id: str, blob_name: str) -> str:
    """
    Enqueue JSON {"post_id": "...", "blob_name": "..."} dans process-image.
    Retourne l'id du message.
    """
    qc = get_queue_client()
    payload = json.dumps({"post_id": post_id, "blob_name": blob_name})
    resp = qc.send_message(payload)
    return resp.id

