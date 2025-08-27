from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, constr
from bson import ObjectId
from ..deps import get_db
from ..deps_auth import get_current_user_id
from ..services.auth_service import (
    hash_password, verify_password, normalize_username,
    issue_tokens, rotate_refresh, revoke_refresh, generate_recovery_code
)
from argon2 import PasswordHasher
from datetime import datetime

router = APIRouter()

Username = constr(pattern=r"^[a-zA-Z0-9_]{3,20}$")

class SignupRequest(BaseModel):
    username: Username
    password: constr(min_length=8)
    display_name: constr(min_length=1, max_length=40)

class LoginRequest(BaseModel):
    username: str
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class ResetRequest(BaseModel):
    username: str
    recovery_code: str
    new_password: constr(min_length=8)

@router.post("/signup")
async def signup(body: SignupRequest, db=Depends(get_db)):
    username, username_ci = normalize_username(body.username)
    exists = await db.users.find_one({"username_ci": username_ci})
    if exists:
        raise HTTPException(409, "username_taken")
    rec = generate_recovery_code()
    doc = {
        "username": username,
        "username_ci": username_ci,
        "password_hash": hash_password(body.password),
        "recovery_code_hash": PasswordHasher().hash(rec),
        "display_name": body.display_name,
        "avatar_url": None,
        "showcase": [], "followers": [], "following": [],
        "xp": 0,
        "created_at": datetime.utcnow(),
    }
    res = await db.users.insert_one(doc)
    user_out = {"id": str(res.inserted_id), "username": username, "display_name": body.display_name, "avatar_url": None}
    return {"user": user_out, "recovery_code": rec}

@router.post("/login")
async def login(body: LoginRequest, db=Depends(get_db)):
    _, username_ci = normalize_username(body.username)
    user = await db.users.find_one({"username_ci": username_ci})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "bad_credentials")
    toks = await issue_tokens(db, str(user["_id"]))
    return {"access_token": toks["access_token"], "refresh_token": toks["refresh_token"], "user": {
        "id": str(user["_id"]), "username": user["username"], "display_name": user["display_name"], "avatar_url": user.get("avatar_url")
    }}

@router.post("/token/refresh")
async def refresh(body: RefreshRequest, db=Depends(get_db)):
    try:
        toks = await rotate_refresh(db, body.refresh_token)
        return {"access_token": toks["access_token"]}
    except ValueError as e:
        raise HTTPException(401, str(e))

@router.post("/logout")
async def logout(body: RefreshRequest, db=Depends(get_db)):
    await revoke_refresh(db, body.refresh_token)
    return {"ok": True}

@router.post("/password/reset")
async def reset(body: ResetRequest, db=Depends(get_db)):
    _, username_ci = normalize_username(body.username)
    user = await db.users.find_one({"username_ci": username_ci})
    if not user:
        raise HTTPException(404, "user_not_found")
    try:
        PasswordHasher().verify(user["recovery_code_hash"], body.recovery_code)
    except Exception:
        raise HTTPException(400, "bad_recovery")
    await db.users.update_one({"_id": user["_id"]}, {"$set":{"password_hash": hash_password(body.new_password)}})
    return {"ok": True}
    
@router.get("/me-test")
async def me_test(user_id: str = Depends(get_current_user_id)):
    return {"user_id": user_id}

