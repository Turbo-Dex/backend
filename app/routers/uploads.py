from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from ..config import settings
from ..services.storage_service import create_sas_for_upload, create_blob_name
from ..deps_auth import get_current_user_id

router = APIRouter()

class SASRequest(BaseModel):
    mime: str
    size: int  # bytes

@router.post("/sas")
async def get_sas(req: SASRequest, user_id: str = Depends(get_current_user_id)):
    size_mb = (req.size + (1024*1024 - 1)) // (1024*1024)
    if size_mb > settings.MAX_UPLOAD_MB:
        raise HTTPException(status_code=413, detail="payload_too_large")
    try:
        blob_name = create_blob_name(req.mime)
        return create_sas_for_upload(blob_name, req.mime, size_mb)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
