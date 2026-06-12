import logging
import secrets
from typing import Any, List, Union

import aiosqlite

logger = logging.getLogger(__name__)

ContentType = Union[str, list]


class ChatMessage:
    def __init__(self, role: str, content: ContentType):
        self.role = role
        self.content = content

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}

    @classmethod
    def from_text(cls, role: str, text: str):
        return cls(role=role, content=text)

    @classmethod
    def from_photo(cls, caption: str, base64_data: str, mime: str = "image/jpeg"):
        content: ContentType = [
            {"type": "text", "text": caption or "Что на изображении?"},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64_data}"}},
        ]
        return cls(role="user", content=content)

    def display_text(self) -> str:
        if isinstance(self.content, str):
            return self.content
        parts = []
        for part in self.content:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(part["text"])
        return " | ".join(parts) if parts else "[медиа]"


class ConversationHistory:
    def __init__(self, db: aiosqlite.Connection, limit: int = 20):
        self._db = db
        self._limit = limit

    async def add(self, chat_id: int, role: str, content: str):
        await self._db.execute(
            "INSERT INTO conversations (chat_id, role, content) VALUES (?, ?, ?)",
            (chat_id, role, content),
        )
        await self._db.commit()
        await self._trim(chat_id)

    async def _trim(self, chat_id: int):
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM conversations WHERE chat_id = ?",
            (chat_id,),
        )
        row = await cursor.fetchone()
        if not row or row[0] <= self._limit:
            return
        excess = row[0] - self._limit
        await self._db.execute(
            "DELETE FROM conversations WHERE id IN ("
            "SELECT id FROM conversations WHERE chat_id = ? "
            "ORDER BY created_at ASC LIMIT ?"
            ")",
            (chat_id, excess),
        )
        await self._db.commit()

    async def get(self, chat_id: int) -> List[ChatMessage]:
        cursor = await self._db.execute(
            "SELECT role, content FROM conversations "
            "WHERE chat_id = ? ORDER BY created_at ASC",
            (chat_id,),
        )
        rows = await cursor.fetchall()
        return [ChatMessage(role=r[0], content=r[1]) for r in rows]

    async def get_dicts(self, chat_id: int) -> List[dict]:
        msgs = await self.get(chat_id)
        return [m.to_dict() for m in msgs]

    async def clear(self, chat_id: int) -> int:
        cursor = await self._db.execute(
            "DELETE FROM conversations WHERE chat_id = ?",
            (chat_id,),
        )
        await self._db.commit()
        count = cursor.rowcount
        logger.info("History cleared for chat %s (%d messages)", chat_id, count)
        return count


class SessionManager:
    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def get_or_create(self, chat_id: int) -> str:
        cursor = await self._db.execute(
            "SELECT session_id FROM sessions WHERE chat_id = ?",
            (chat_id,),
        )
        row = await cursor.fetchone()
        if row:
            return row[0]
        session_id = f"tg_{chat_id}"
        await self._db.execute(
            "INSERT INTO sessions (chat_id, session_id) VALUES (?, ?)",
            (chat_id, session_id),
        )
        await self._db.commit()
        logger.info("Created session %s for chat %s", session_id, chat_id)
        return session_id

    async def rotate(self, chat_id: int) -> str:
        suffix = secrets.token_hex(4)
        session_id = f"tg_{chat_id}_{suffix}"
        await self._db.execute(
            "INSERT OR REPLACE INTO sessions (chat_id, session_id) VALUES (?, ?)",
            (chat_id, session_id),
        )
        await self._db.commit()
        logger.info("Rotated session for chat %s: %s", chat_id, session_id)
        return session_id

    async def remove(self, chat_id: int):
        await self._db.execute(
            "DELETE FROM sessions WHERE chat_id = ?",
            (chat_id,),
        )
        await self._db.commit()


class ModelManager:
    def __init__(self, db: aiosqlite.Connection, default: str):
        self._db = db
        self._default = default

    async def get(self, chat_id: int) -> str:
        cursor = await self._db.execute(
            "SELECT model FROM model_preferences WHERE chat_id = ?",
            (chat_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else self._default

    async def set(self, chat_id: int, model: str):
        await self._db.execute(
            "INSERT OR REPLACE INTO model_preferences (chat_id, model) VALUES (?, ?)",
            (chat_id, model),
        )
        await self._db.commit()
