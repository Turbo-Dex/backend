import uuid, jwt
from datetime import datetime, timedelta, timezone
from ..config import settings

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def new_jti() -> str:
    return uuid.uuid4().hex
    
def _safe_minutes(val, default=15) -> int:
    try:
        v = int(val)
    except Exception:
        v = default
    if v <= 0:
        v = default
    return v

def create_access_token(sub: str) -> str:
    iat = now_utc()
    mins = _safe_minutes(settings.JWT_ACCESS_MIN, default=15)
    exp = iat + timedelta(minutes=mins)
    # timestamps cohérents
    payload = {
        "sub": sub,
        "iat": int(iat.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

def create_refresh_token(sub: str) -> tuple[str, str, int]:
    jti = new_jti()
    iat = now_utc()
    days = _safe_minutes(settings.JWT_REFRESH_DAYS, default=14)
    exp = iat + timedelta(days=days)
    payload = {
        "sub": sub,
        "jti": jti,
        "iat": int(iat.timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, settings.JWT_REFRESH_SECRET, algorithm="HS256")
    return token, jti, int(exp.timestamp())
