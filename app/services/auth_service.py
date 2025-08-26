from argon2 import PasswordHasher
from argon2.low_level import Type
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
import jwt
from ..utils.security import create_access_token, create_refresh_token

ph = PasswordHasher(time_cost=2, memory_cost=102400, parallelism=8, hash_len=32, type=Type.ID)

def hash_password(pw: str) -> str:
    return ph.hash(pw)

def verify_password(pw: str, h: str) -> bool:
    try:
        return ph.verify(h, pw)
    except Exception:
        return False

def normalize_username(u: str) -> tuple[str,str]:
    return u, u.lower()

async def issue_tokens(db: AsyncIOMotorDatabase, user_id: str) -> dict:
    access = create_access_token(user_id)
    refresh, jti, exp = create_refresh_token(user_id)
    await db.refresh_tokens.insert_one({
        "user_id": user_id, "jti": jti, "exp": exp, "revoked": False, "created_at": datetime.utcnow()
    })
    return {"access_token": access, "refresh_token": refresh}

async def rotate_refresh(db: AsyncIOMotorDatabase, refresh_token: str) -> dict:
    from ..config import settings
    try:
        payload = jwt.decode(refresh_token, settings.JWT_REFRESH_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise ValueError("invalid_refresh")
    row = await db.refresh_tokens.find_one({"user_id": payload["sub"], "jti": payload.get("jti")})
    if not row or row.get("revoked"):
        # reuse detection: invalide tout
        await db.refresh_tokens.update_many({"user_id": payload.get("sub")}, {"$set":{"revoked": True}})
        raise ValueError("reuse_detected")
    await db.refresh_tokens.update_one({"_id": row["_id"]}, {"$set": {"revoked": True}})
    return await issue_tokens(db, payload["sub"])

async def revoke_refresh(db: AsyncIOMotorDatabase, refresh_token: str):
    from ..config import settings
    try:
        payload = jwt.decode(refresh_token, settings.JWT_REFRESH_SECRET, algorithms=["HS256"])
        await db.refresh_tokens.update_one({"user_id": payload["sub"], "jti": payload.get("jti")}, {"$set": {"revoked": True}})
    except jwt.PyJWTError:
        return

def generate_recovery_code(n: int = 12) -> str:
    import secrets, string
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))
