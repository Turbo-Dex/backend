from motor.motor_asyncio import AsyncIOMotorDatabase

async def ensure_indexes(db: AsyncIOMotorDatabase):
    await db.posts.create_index([("created_at",-1), ("_id",-1)], name="post_feed_idx")
    await db.turbodex.create_index([("user_id",1), ("vehicle_key",1)], name="user_vehicle_unique", unique=True)
