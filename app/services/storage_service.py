from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from ..config import settings
import re, uuid, datetime as dt

SAFE_MIME = {"image/jpeg","image/png","image/webp"}
EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}

_client: BlobServiceClient | None = None

def _svc() -> BlobServiceClient:
    global _client
    if _client is None:
        _client = BlobServiceClient.from_connection_string(settings.AZURE_STORAGE_CONNECTION_STRING)
    return _client

def sanitize(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9/_\-.]", "_", name)

def create_blob_name(mime: str) -> str:
    ext = EXT.get(mime, ".bin")
    return f"{dt.datetime.utcnow():%Y%m%d}/{uuid.uuid4().hex}{ext}"

def create_sas_for_upload(blob_name: str, mime: str, size_max_mb: int, minutes: int = 15) -> dict:
    if mime not in SAFE_MIME:
        raise ValueError("bad_mime")
    blob_name = sanitize(blob_name)
    expiry = datetime.utcnow() + timedelta(minutes=minutes)
    sas = generate_blob_sas(
        account_name=_svc().account_name,
        container_name=settings.AZURE_BLOB_CONTAINER_RAW,
        blob_name=blob_name,
        permission=BlobSasPermissions(create=True, write=True),
        expiry=expiry,
    )
    url = f"{_svc().url}/{settings.AZURE_BLOB_CONTAINER_RAW}/{blob_name}?{sas}"
    return {
        "sas_url": url,
        "blob_name": blob_name,
        "expires_at": expiry.isoformat(),
        "max_size": size_max_mb * 1024 * 1024,
    }

def public_url(container: str, blob_name: str) -> str:
    return f"{_svc().url}/{container}/{blob_name}"
