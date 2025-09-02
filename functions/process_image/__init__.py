import json
import logging
import os
from pathlib import Path
from datetime import datetime

import azure.functions as func

# ⚠️ Ne crée PAS de clients au module-level avec os.environ["..."].
# Utilise getenv + instancie dans main() = évite crash au import.

def main(msg: func.QueueMessage) -> None:
    # 1) Log brut du message (pour voir qu’on est bien entré dans la fonction)
    raw = msg.get_body().decode("utf-8", errors="replace")
    logging.info("[process_image] raw_message=%r", raw[:500])

    # 2) Parse JSON
    try:
        data = json.loads(raw)
    except Exception:
        logging.exception("[process_image] invalid JSON -> ack (pas de poison)")
        return

    post_id = data.get("post_id")
    blob_name = data.get("blob_name")
    logging.info("[process_image] parsed post_id=%s blob_name=%s", post_id, blob_name)

    # 3) Envs (sans planter si manquants)
    #    On accepte AzureWebJobsStorage ou StorageConn (fallback).
    storage_cs = os.getenv("AzureWebJobsStorage") or os.getenv("StorageConn")
    cont_raw = os.getenv("AZURE_BLOB_CONTAINER_RAW", "raw")
    cont_out = os.getenv("AZURE_BLOB_CONTAINER_PROCESSED", "processed")
    blur_api = os.getenv("BLUR_API")
    predict_api = os.getenv("PREDICT_API")

    missing = []
    if not storage_cs: missing.append("AzureWebJobsStorage/StorageConn")
    if not cont_raw:   missing.append("AZURE_BLOB_CONTAINER_RAW")
    if not cont_out:   missing.append("AZURE_BLOB_CONTAINER_PROCESSED")

    if missing:
        logging.error("[process_image] missing envs: %s -> ack (pas de poison)", ", ".join(missing))
        return

    # 4) Marqueur local (utile pour prouver l’exécution sur ta machine)
    try:
        Path("/tmp/func_marker").write_text(f"ok {datetime.utcnow().isoformat()} blob={blob_name}\n", encoding="utf-8")
    except Exception:
        pass

    # 5) No-op minimal : on ack directement (objectif: sortir du poison)
    #    Une fois stable, on réactivera le vrai pipeline (download -> blur -> predict -> upload -> update mongo)
    logging.info("[process_image] NO-OP success (ack).")
    return

