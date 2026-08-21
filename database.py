import aiosqlite
import logging
from typing import Any, Dict, List, Optional
import config

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = config.DB_PATH):
        self.db_path = db_path

    async def init_db(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id INTEGER PRIMARY KEY,
                    chat_title TEXT,
                    chat_type TEXT,
                    interval_minutes INTEGER DEFAULT 30,
                    is_active INTEGER DEFAULT 1
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS served_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER,
                    question_id TEXT
                )
            """)
            await db.commit()

    async def register_or_update_chat(self, chat_id: int, title: str = "", chat_type: str = "group", is_active: Optional[bool] = None) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT is_active FROM chats WHERE chat_id = ?", (chat_id,)) as cur:
                row = await cur.fetchone()
            if row is None:
                active_val = 1 if is_active is None or is_active else 0
                await db.execute(
                    "INSERT INTO chats (chat_id, chat_title, chat_type, interval_minutes, is_active) VALUES (?, ?, ?, ?, ?)",
                    (chat_id, title, chat_type, config.DEFAULT_QUIZ_INTERVAL_MINUTES, active_val),
                )
            else:
                if is_active is not None:
                    await db.execute("UPDATE chats SET chat_title = ?, chat_type = ?, is_active = ? WHERE chat_id = ?", (title, chat_type, 1 if is_active else 0, chat_id))
                else:
                    await db.execute("UPDATE chats SET chat_title = ?, chat_type = ? WHERE chat_id = ?", (title, chat_type, chat_id))
            await db.commit()

    async def set_chat_interval(self, chat_id: int, interval_minutes: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE chats SET interval_minutes = ?, is_active = 1 WHERE chat_id = ?", (interval_minutes, chat_id))
            await db.commit()

    async def set_chat_active_status(self, chat_id: int, is_active: bool) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE chats SET is_active = ? WHERE chat_id = ?", (1 if is_active else 0, chat_id))
            await db.commit()

    async def get_chat_settings(self, chat_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM chats WHERE chat_id = ?", (chat_id,)) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def get_all_active_chats(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM chats WHERE is_active = 1") as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]

    async def record_served_question(self, chat_id: int, question_id: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO served_questions (chat_id, question_id) VALUES (?, ?)", (chat_id, question_id))
            await db.commit()

    async def get_served_question_ids(self, chat_id: int) -> set[str]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT question_id FROM served_questions WHERE chat_id = ?", (chat_id,)) as cur:
                rows = await cur.fetchall()
                return {r[0] for r in rows}

    async def reset_served_questions_for_chat(self, chat_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM served_questions WHERE chat_id = ?", (chat_id,))
            await db.commit()
