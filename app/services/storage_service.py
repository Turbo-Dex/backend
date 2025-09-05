# app/services/storage_service.py
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from ..config import settings
import re, uuid, datetime as dt

SAFE_MIME = {"image/jpeg","image/png","image/webp"}
EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}

_client: BlobServiceClient | None = None

def _clean_path(*parts: str) -> str:
    # join sans double slash
    cleaned = [p.strip("/") for p in parts if p is not None]
    return "/".join(cleaned)
    
def _account_info_from_conn_str(cs: str) -> tuple[str | None, str | None]:
    parts = {}
    for seg in cs.split(";"):
        if "=" in seg:
            k, v = seg.split("=", 1)
            parts[k.strip()] = v.strip()
    return parts.get("AccountName"), parts.get("AccountKey")

def _svc() -> BlobServiceClient:
    global _client
    if _client is None:
        _client = BlobServiceClient.from_connection_string(settings.AZURE_STORAGE_CONN)
    return _client

def _account_info_from_conn_str(cs: str) -> tuple[str | None, str | None]:
    """
    Parse 'AccountName=...;AccountKey=...;...' from a standard storage connection string.
    """
    parts = {}
    for seg in cs.split(";"):
        if "=" in seg:
            k, v = seg.split("=", 1)
            parts[k.strip()] = v.strip()
    return parts.get("AccountName"), parts.get("AccountKey")

def sanitize(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9/_\-.]", "_", name)

def create_blob_name(mime: str) -> str:
    ext = EXT.get(mime, ".bin")
    return f"{dt.datetime.utcnow():%Y%m%d}/{uuid.uuid4().hex}{ext}"

def create_sas_for_upload(blob_name: str, mime: str, size_max_mb: int, minutes: int = 15) -> dict:
    if mime not in SAFE_MIME:
        raise ValueError("bad_mime")

    # Récupère AccountName/AccountKey depuis la connection string
    account_name, account_key = _account_info_from_conn_str(settings.AZURE_STORAGE_CONN)
    if not account_name or not account_key:
        raise ValueError("missing_account_key")

    # Noms propres (évite les doubles slash)
    container = settings.AZURE_BLOB_CONTAINER_RAW.strip("/")
    blob_name = blob_name.lstrip("/")

    # Expiration de la SAS (UTC)
    expiry = datetime.utcnow() + timedelta(minutes=minutes)

    # Génère la SAS avec la clé de compte (permissions: create + write)
    sas = generate_blob_sas(
        account_name=account_name,
        container_name=container,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(create=True, write=True),
        expiry=expiry,
    )

    # Construit l’URL finale propre (sans //)
    base = _svc().url.rstrip("/")  # ex: https://<account>.blob.core.windows.net
    url = f"{base}/{_clean_path(container, blob_name)}?{sas}"

    return {
        "sas_url": url,
        "blob_name": blob_name,
        "expires_at": expiry.isoformat(),
        "max_size": size_max_mb * 1024 * 1024,
    }
    
def public_url(container: str, blob_name: str) -> str:
    base = _svc().url.rstrip("/")
    return f"{base}/{_clean_path(container, blob_name)}"

