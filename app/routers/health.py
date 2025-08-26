from fastapi import APIRouter
from datetime import datetime, timezone

router = APIRouter()

@router.get("")
async def health():
    return {
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat()
    }
