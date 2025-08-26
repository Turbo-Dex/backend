import uuid, jwt
from datetime import datetime, timedelta
from ..config import settings

def now_utc() -> datetime:
    return datetime.utcnow()

def new_jti() -> str:
    return uuid.uuid4().hex

def create_access_token(sub: str) -> str:
    iat = now_utc(); exp = iat + timedelta(minutes=settings.JWT_ACCESS_MIN)
    payload = {"sub": sub, "iat": int(iat.timestamp()), "exp": int(exp.timestamp())}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

def create_refresh_token(sub: str) -> tuple[str, str, int]:
    jti = new_jti()
    iat = now_utc(); exp = iat + timedelta(days=settings.JWT_REFRESH_DAYS)
    payload = {"sub": sub, "jti": jti, "iat": int(iat.timestamp()), "exp": int(exp.timestamp())}
    token = jwt.encode(payload, settings.JWT_REFRESH_SECRET, algorithm="HS256")
    return token, jti, int(exp.timestamp())
