# process_image/__init__.py
import base64
import json
import logging
import mimetypes
import os
from datetime import datetime
from io import BytesIO
from typing import Tuple, Optional, Dict, Any

import azure.functions as func
import requests
from azure.storage.blob import BlobServiceClient

# Mongo est optionnel en local
try:
    from pymongo import MongoClient
    from bson import ObjectId
except Exception:  # pragma: no cover
    MongoClient = None
    ObjectId = None


# ====== Config / Env ======
RAW_CONT = os.getenv("AZURE_BLOB_CONTAINER_RAW", "raw")
PROC_CONT = os.getenv("AZURE_BLOB_CONTAINER_PROCESSED", "processed")

BLUR_URL = (os.getenv("IA_BLUR_URL") or "").strip()  # ex: http://172.189.95.209/blur/
PREDICT_URL = (os.getenv("IA_PREDICT_URL") or os.getenv("PREDICT_URL") or "").strip()  # ex: http://20.19.112.183/predict/

# normaliser PREDICT_URL avec un slash final (évite les 307 -> /predict/)
if PREDICT_URL and not PREDICT_URL.endswith("/"):
    PREDICT_URL += "/"

HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT_SECONDS", "20"))


# ====== Helpers Blob / Mongo / HTTP ======
def _blob_client() -> BlobServiceClient:
    """
    Récupère un BlobServiceClient à partir de la chaîne de connexion.
    Utilise AzureWebJobsStorage (requis par les Triggers) ou StorageConn (fallback).
    """
    cs = os.environ.get("AzureWebJobsStorage") or os.environ.get("StorageConn")
    if not cs:
        raise RuntimeError("AzureWebJobsStorage/StorageConn missing")
    return BlobServiceClient.from_connection_string(cs)


def _mongo() -> Tuple[Optional[MongoClient], Optional[Any]]:
    """
    Ouvre une connexion Mongo si MONGO_URI est présent et pymongo dispo.
    Retourne (client, db) ou (None, None) si non dispo.
    """
    uri = os.getenv("MONGO_URI")
    dbn = os.getenv("DB_NAME", "turbodex")
    if not uri or MongoClient is None:
        return None, None
    try:
        cli = MongoClient(uri, serverSelectionTimeoutMS=3000)
        cli.admin.command("ping")
        return cli, cli[dbn]
    except Exception as e:  # ne pas faire planter la fonction si Mongo HS
        logging.warning("[process_image] Mongo unreachable: %s", e)
        return None, None


def _http_post_image(
    url: str,
    field_name: str,
    filename: str,
    content: bytes,
    mime: Optional[str] = None,
    accept: Optional[str] = None,
) -> requests.Response:
    """
    Envoie un fichier via multipart (champ `field_name`), gère raise_for_status avec log.
    """
    if not mime:
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    files = {field_name: (filename, content, mime)}
    headers = {}
    if accept:
        headers["Accept"] = accept

    r = requests.post(url, files=files, headers=headers, timeout=HTTP_TIMEOUT, allow_redirects=True)
    try:
        r.raise_for_status()
    except Exception:
        # Log utile au debug
        try:
            logging.error("[process_image] HTTP POST %s -> %s %s", url, r.status_code, (r.text or "")[:500])
        except Exception:
            pass
        raise
    return r


def _predict_call(img_bytes: bytes, filename: str, mime: str) -> Optional[Dict[str, Any]]:
    """
    Appelle l’API de prédiction.
    Essaie d’abord avec le champ 'file' (ce que montre ton 422), puis 'image' en fallback.
    Retourne le JSON (dict) ou None en cas d’échec.
    """
    if not PREDICT_URL:
        return None

    url = PREDICT_URL  # déjà normalisé avec un slash final au chargement
    last_err = ""

    for field in ("file", "image"):
        try:
            r = requests.post(
                url,
                files={field: (filename, img_bytes, mime)},
                headers={"Accept": "application/json"},
                timeout=HTTP_TIMEOUT,
                allow_redirects=True,
            )
            try:
                r.raise_for_status()
            except Exception:
                # si 422 "Field required", on essaie le champ suivant
                if r.status_code == 422:
                    logging.warning(
                        "[process_image] predict HTTP 422 for field '%s' -> trying fallback", field
                    )
                    last_err = (r.text or "")[:500]
                    continue
                # autre erreur: log et stop
                logging.error("[process_image] predict HTTP %s: %s", r.status_code, (r.text or "")[:500])
                raise
            # OK
            return r.json()
        except Exception as e:
            last_err = str(e)

    logging.warning("[process_image] predict failed after tries: %s", last_err)
    return None


def _parse_queue_json(raw: bytes) -> Dict[str, Any]:
    """
    Tente de parser le contenu du message queue:
      - en JSON texte
      - sinon en base64 -> JSON
    Lève ValueError si rien ne marche.
    """
    # 1) essai direct JSON texte
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        pass

    # 2) essai base64 -> json
    try:
        decoded = base64.b64decode(raw, validate=True)
        return json.loads(decoded.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"cannot decode queue message as JSON or Base64 JSON: {e}") from e


# ====== Main Function ======
def main(msg: func.QueueMessage) -> None:
    # Lire le message (JSON direct ou Base64 JSON)
    raw_body = msg.get_body()
    try:
        data = _parse_queue_json(raw_body)
    except Exception:
        logging.exception("[process_image] invalid message (not JSON / Base64 JSON): %r", raw_body[:200])
        # Ne relance pas d'exception -> évite poison
        return

    post_id = data.get("post_id")
    blob_name = data.get("blob_name")
    logging.info("[process_image] parsed post_id=%s blob_name=%s", post_id, blob_name)

    if not blob_name:
        logging.error("[process_image] missing 'blob_name' in message")
        return

    # 1) Download RAW depuis le container "raw"
    try:
        bsc = _blob_client()
        raw_blob = bsc.get_blob_client(container=RAW_CONT, blob=blob_name)
        raw_bytes = raw_blob.download_blob().readall()
        logging.info("[process_image] downloaded raw bytes=%d", len(raw_bytes))
    except Exception as e:
        logging.exception("[process_image] failed to download raw: %s", e)
        return  # échec non réessayé plusieurs fois inutilement (mais le runtime fera 5 essais par défaut)

    processed_bytes = raw_bytes
    processed_mime = "image/jpeg"  # par défaut

    # 2) Blur API si configurée
    if BLUR_URL:
        try:
            r_blur = _http_post_image(
                url=BLUR_URL,
                field_name="file",  # confirmé par tes cURL
                filename=os.path.basename(blob_name) or "image.jpg",
                content=raw_bytes,
                mime="image/jpeg",
                accept="image/png",  # l’API blur répond en PNG
            )
            processed_bytes = r_blur.content
            processed_mime = r_blur.headers.get("Content-Type") or "image/png"
            logging.info("[process_image] blur ok bytes=%d mime=%s", len(processed_bytes), processed_mime)
        except Exception as e:
            logging.warning("[process_image] blur failed, using raw: %s", e)

    # 3) Predict API si configurée
    tags_payload: Optional[Dict[str, Any]] = None
    if PREDICT_URL:
        try:
            # si blur -> probable PNG, sinon JPEG
            predict_mime = processed_mime or "image/jpeg"
            tags_payload = _predict_call(
                processed_bytes,
                os.path.basename(blob_name) or ("image.png" if predict_mime == "image/png" else "image.jpg"),
                predict_mime,
            )
            if isinstance(tags_payload, dict):
                logging.info(
                    "[process_image] predict ok keys=%s",
                    list(tags_payload.keys()),
                )
            else:
                logging.warning("[process_image] predict returned no JSON")
        except Exception as e:
            # _predict_call() est déjà tolérant, mais par sécurité
            logging.warning("[process_image] predict failed: %s", e)
            tags_payload = None

    # 4) Upload processed dans le container "processed"
    try:
        proc_blob = bsc.get_blob_client(container=PROC_CONT, blob=blob_name)
        proc_blob.upload_blob(
            processed_bytes,
            overwrite=True,
            content_type=processed_mime or "application/octet-stream",
        )
        logging.info("[process_image] uploaded processed %s/%s", PROC_CONT, blob_name)
    except Exception as e:
        logging.exception("[process_image] failed to upload processed: %s", e)
        return

        # 5) Update Mongo (si dispo)
    cli, db = _mongo()
    if (db is not None) and isinstance(post_id, str) and len(post_id) == 24 and (ObjectId is not None):
        try:
            update_doc: Dict[str, Any] = {
                "status": "processed",
                "processed_blob_url": proc_blob.url,  # nécessite conteneur public ou SAS côté app
                "processed_at": datetime.utcnow(),
            }
            if isinstance(tags_payload, dict):
                update_doc["ai"] = {
                    "raw": tags_payload,
                    "tags": tags_payload.get("tags") if isinstance(tags_payload, dict) else None,
                }

            db.posts.update_one({"_id": ObjectId(post_id)}, {"$set": update_doc})
            logging.info("[process_image] mongo updated post_id=%s", post_id)
        except Exception as e:
            # On ne souhaite pas poison la queue pour Mongo HS
            logging.warning("[process_image] mongo update skipped: %s", e)

    logging.info("[process_image] done.")


