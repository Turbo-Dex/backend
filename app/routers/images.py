# app/routers/images.py
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional, List
from uuid import uuid4

from fastapi import APIRouter, UploadFile, File, HTTPException, status

from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.storage.queue import QueueClient
from azure.storage.queue._message_encoding import TextBase64EncodePolicy

from app.config import settings

router = APIRouter()

# ------------------------------
# Helpers connexion / utils
# ------------------------------

def _conn_str() -> str:
    """
    Ordre de priorité :
      1) settings.AZURE_STORAGE_CONN
      2) env AzureWebJobsStorage
      3) env StorageConn
      4) fallback (AZURE_STORAGE_ACCOUNT + AZURE_STORAGE_KEY)
    """
    c = (
        (getattr(settings, "AZURE_STORAGE_CONN", None) or "").strip()
        or (os.getenv("AzureWebJobsStorage") or "").strip()
        or (os.getenv("StorageConn") or "").strip()
    )
    if not c:
        acc = (
            getattr(settings, "AZURE_STORAGE_ACCOUNT", None)
            or os.getenv("AZURE_STORAGE_ACCOUNT")
            or ""
        ).strip()
        key = (
            getattr(settings, "AZURE_STORAGE_KEY", None)
            or os.getenv("AZURE_STORAGE_KEY")
            or ""
        ).strip()
        if acc and key:
            c = (
                f"DefaultEndpointsProtocol=https;"
                f"AccountName={acc};AccountKey={key};EndpointSuffix=core.windows.net"
            )
    if not c:
        raise RuntimeError(
            "Aucune chaîne de connexion Azure Storage trouvée "
            "(AZURE_STORAGE_CONN / AzureWebJobsStorage / StorageConn)."
        )
    return c


def _account_from_conn_string(cs: str) -> Optional[str]:
    m = re.search(r"AccountName=([^;]+)", cs or "")
    return m.group(1) if m else None


def _guess_ext(content_type: str) -> str:
    ct = (content_type or "").lower()
    if ct in ("image/jpeg", "image/jpg"):
        return ".jpg"
    if ct == "image/png":
        return ".png"
    if ct == "image/webp":
        return ".webp"
    return ""


def _public_blob_url(account: Optional[str], container: str, blob_name: str) -> Optional[str]:
    # Valable si le conteneur est public (sinon juste indicatif)
    if not account:
        return None
    return f"https://{account}.blob.core.windows.net/{container}/{blob_name}"


# Paramètres (containers / queue)
RAW_CONT = getattr(settings, "AZURE_BLOB_CONTAINER_RAW", "raw") or "raw"
PROC_CONT = getattr(settings, "AZURE_BLOB_CONTAINER_PROCESSED", "processed") or "processed"
QUEUE_NAME = getattr(settings, "AZURE_QUEUE_NAME", "process-image") or "process-image"


# ------------------------------
# Diag
# ------------------------------

@router.get("/diag")
def images_diag():
    cs = (
        (getattr(settings, "AZURE_STORAGE_CONN", None) or "").strip()
        or (os.getenv("AzureWebJobsStorage") or "").strip()
        or (os.getenv("StorageConn") or "").strip()
    )
    return {
        "storage_conn_present": bool(cs),
        "account_hint": _account_from_conn_string(cs),
        "raw_container": RAW_CONT,
        "processed_container": PROC_CONT,
        "queue": QUEUE_NAME,
    }


@router.get("/diag/queue-peek")
def diag_queue_peek(limit: int = 3):
    """Petit coup d'œil non destructif dans la queue (max 32 côté service)."""
    conn = _conn_str()
    q = QueueClient.from_connection_string(
        conn,
        queue_name=QUEUE_NAME,
        message_encode_policy=TextBase64EncodePolicy(),
    )
    msgs = list(q.peek_messages(max_messages=min(max(limit, 1), 32)))
    # On ne retourne pas le contenu exact pour éviter d’exposer des payloads en clair
    return {"queue": QUEUE_NAME, "peek_count": len(msgs)}


# ------------------------------
# Endpoints
# ------------------------------

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile = File(..., description="Image à uploader"),
    post_id: Optional[str] = None,
):
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="Aucun fichier reçu.")
    if file.content_type not in {"image/jpeg", "image/jpg", "image/png", "image/webp"}:
        raise HTTPException(status_code=415, detail=f"Type non supporté: {file.content_type}")

    # nommage: YYYYMMDD/uuid.ext
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    ext = _guess_ext(file.content_type) or os.path.splitext(file.filename)[1] or ".jpg"
    blob_name = f"{today}/{uuid4().hex}{ext}"

    # Connexion Storage
    conn = _conn_str()
    account = _account_from_conn_string(conn)

    # Upload dans RAW
    bsc = BlobServiceClient.from_connection_string(conn)
    raw_client = bsc.get_blob_client(container=RAW_CONT, blob=blob_name)

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Fichier vide.")

    raw_client.upload_blob(
        data,
        overwrite=True,
        content_settings=ContentSettings(content_type=file.content_type),
    )

    # Enqueue le message pour la Function (Base64 requis par host.json)
    q = QueueClient.from_connection_string(
        conn,
        queue_name=QUEUE_NAME,
        message_encode_policy=TextBase64EncodePolicy(),
    )
    try:
        q.create_queue()
    except Exception:
        pass

    payload = {
        "post_id": (post_id or "000000000000000000000000"),
        "blob_name": blob_name,
    }

    try:
        send_result = q.send_message(json.dumps(payload))
        msg_id = getattr(send_result, "id", None)  # string attendue
    except Exception as e:
        logging.exception("Queue send_message failed")
        raise HTTPException(status_code=502, detail=f"Queue send failed: {e}")

    logging.info("[images.upload] sent queue msg id=%s queue=%s blob=%s",
                 msg_id, QUEUE_NAME, blob_name)

    return {
        "ok": True,
        "blob_name": blob_name,
        "raw_url": _public_blob_url(account, RAW_CONT, blob_name),
        "processed_url_hint": _public_blob_url(account, PROC_CONT, blob_name),
        "queue": QUEUE_NAME,
        "message_id": msg_id,     # <-- FIX: renvoi direct de la string
        "message_payload": payload,
        "storage_account": account,
    }


@router.get("/status")
def status_image(blob_name: str):
    """
    Vérifie si l’image traitée existe dans 'processed'.
    Tente plusieurs suffixes si besoin (.png/.jpg) car la Function peut ré-encoder.
    """
    if not blob_name or "/" not in blob_name:
        raise HTTPException(status_code=400, detail="blob_name invalide")

    conn = _conn_str()
    account = _account_from_conn_string(conn)
    bsc = BlobServiceClient.from_connection_string(conn)

    # Essaye tel quel + variantes d’extension
    candidates: List[str] = [blob_name]
    if not os.path.splitext(blob_name)[1]:
        candidates += [f"{blob_name}.png", f"{blob_name}.jpg", f"{blob_name}.jpeg"]

    for name in candidates:
        proc_client = bsc.get_blob_client(container=PROC_CONT, blob=name)
        if proc_client.exists():
            return {
                "blob_name": name,
                "processed_exists": True,
                "processed_url": _public_blob_url(account, PROC_CONT, name),
            }

    # Rien trouvé
    return {
        "blob_name": blob_name,
        "processed_exists": False,
        "processed_url": _public_blob_url(account, PROC_CONT, blob_name),
    }
