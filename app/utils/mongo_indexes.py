from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

async def ensure_indexes(db: AsyncIOMotorDatabase):
    await db.users.create_index([("username_ci", ASCENDING)], unique=True, name="uniq_username_ci")
    await db.refresh_tokens.create_index([("user_id", ASCENDING), ("jti", ASCENDING)], unique=True, name="uniq_user_jti")
    await db.posts.create_index([("created_at", DESCENDING), ("_id", DESCENDING)], name="post_feed_idx")

