from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Tuple

class PostCreate(BaseModel):
    blob_name: str
    taken_at: datetime
    gps: Optional[Tuple[float, float]] = None
