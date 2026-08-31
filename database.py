import datetime
import logging
from typing import Any, Dict, List, Optional
import certifi
from motor.motor_asyncio import AsyncIOMotorClient
import config

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, mongo_uri: str = config.MONGO_URI):
        self.client = AsyncIOMotorClient(mongo_uri, tlsCAFile=certifi.where())
        self.db = self.client["quiz_bot_db"]
        
        # Collections
        self.chats = self.db["chats"]
        self.served_questions = self.db["served_questions"]
        self.reports = self.db["reports"]
        self.settings = self.db["system_settings"]
        self.active_polls = self.db["active_polls"]  # 24h auto-delete tracking

    async def init_db(self) -> None:
        try:
            await self.chats.create_index("chat_id", unique=True)
            await self.served_questions.create_index([("chat_id", 1), ("question_id", 1)])
            await self.settings.create_index("key", unique=True)
            await self.active_polls.create_index("poll_id", unique=True)
            await self.active_polls.create_index("created_at")
            logger.info("✅ MongoDB Connected Successfully & Indexes Verified!")
        except Exception as e:
            logger.error(f"Error initializing MongoDB: {e}")

    async def register_or_update_chat(
        self, chat_id: int, title: str = "", chat_type: str = "group", is_active: Optional[bool] = None
    ) -> None:
        update_fields: Dict[str, Any] = {
            "chat_title": title,
            "chat_type": chat_type,
        }
        if is_active is not None:
            update_fields["is_active"] = 1 if is_active else 0

        set_on_insert: Dict[str, Any] = {
            "chat_id": chat_id,
            "interval_minutes": config.DEFAULT_QUIZ_INTERVAL_MINUTES,
        }
        if is_active is None:
            set_on_insert["is_active"] = 1

        await self.chats.update_one(
            {"chat_id": chat_id},
            {
                "$set": update_fields,
                "$setOnInsert": set_on_insert,
            },
            upsert=True,
        )

    async def set_chat_interval(self, chat_id: int, interval_minutes: int) -> None:
        await self.chats.update_one(
            {"chat_id": chat_id},
            {"$set": {"interval_minutes": interval_minutes, "is_active": 1}},
            upsert=True,
        )

    async def set_chat_active_status(self, chat_id: int, is_active: bool) -> None:
        await self.chats.update_one(
            {"chat_id": chat_id},
            {"$set": {"is_active": 1 if is_active else 0}},
        )

    async def get_chat_settings(self, chat_id: int) -> Optional[Dict[str, Any]]:
        return await self.chats.find_one({"chat_id": chat_id})

    async def get_all_active_chats(self) -> List[Dict[str, Any]]:
        cursor = self.chats.find({"is_active": 1})
        return await cursor.to_list(length=None)

    async def get_all_broadcast_chats(self) -> List[Dict[str, Any]]:
        cursor = self.chats.find({})
        return await cursor.to_list(length=None)

    async def get_system_stats(self) -> Dict[str, int]:
        total_users = await self.chats.count_documents({"chat_type": "private"})
        total_groups = await self.chats.count_documents({"chat_type": {"$in": ["group", "supergroup"]}})
        active_groups = await self.chats.count_documents({"chat_type": {"$in": ["group", "supergroup"]}, "is_active": 1})
        return {
            "total_users": total_users,
            "total_groups": total_groups,
            "active_groups": active_groups,
        }

    async def record_served_question(self, chat_id: int, question_id: str) -> None:
        await self.served_questions.insert_one({
            "chat_id": chat_id,
            "question_id": question_id,
            "served_at": datetime.datetime.now(datetime.timezone.utc),
        })

    async def get_served_question_ids(self, chat_id: int) -> set[str]:
        cursor = self.served_questions.find({"chat_id": chat_id}, {"question_id": 1, "_id": 0})
        docs = await cursor.to_list(length=None)
        return {doc["question_id"] for doc in docs if "question_id" in doc}

    async def reset_served_questions_for_chat(self, chat_id: int) -> None:
        await self.served_questions.delete_many({"chat_id": chat_id})

    async def add_report(
        self, chat_id: int, chat_title: str, user_id: int, user_name: str, question_text: str, reason: str
    ) -> str:
        res = await self.reports.insert_one({
            "chat_id": chat_id,
            "chat_title": chat_title,
            "user_id": user_id,
            "user_name": user_name,
            "question_text": question_text,
            "reason": reason,
            "created_at": datetime.datetime.now(datetime.timezone.utc),
        })
        return str(res.inserted_id)[-6:]

    async def set_setting(self, key: str, value: str) -> None:
        await self.settings.update_one(
            {"key": key},
            {"$set": {"key": key, "value": str(value)}},
            upsert=True,
        )

    async def get_setting(self, key: str) -> Optional[str]:
        doc = await self.settings.find_one({"key": key})
        return doc["value"] if doc and "value" in doc else None

    # ---------------- 24-HOUR AUTO-DELETE TRACKING ---------------- #

    async def save_active_poll(self, poll_id: str, chat_id: int, message_id: int) -> None:
        await self.active_polls.update_one(
            {"poll_id": poll_id},
            {
                "$set": {
                    "poll_id": poll_id,
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "created_at": datetime.datetime.now(datetime.timezone.utc),
                }
            },
            upsert=True,
        )

    async def get_expired_polls(self, hours: int = 24) -> List[Dict[str, Any]]:
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)
        cursor = self.active_polls.find({"created_at": {"$lt": cutoff}})
        return await cursor.to_list(length=None)

    async def remove_active_poll(self, poll_id: str) -> None:
        await self.active_polls.delete_one({"poll_id": poll_id})
