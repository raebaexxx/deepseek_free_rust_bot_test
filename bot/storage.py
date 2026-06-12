from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ChatMessage:
    role: str
    content: str

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


class ConversationHistory:
    def __init__(self, limit: int = 20):
        self._limit = limit
        self._data: Dict[int, List[ChatMessage]] = {}

    def add(self, chat_id: int, role: str, content: str):
        if chat_id not in self._data:
            self._data[chat_id] = []
        self._data[chat_id].append(ChatMessage(role=role, content=content))
        if len(self._data[chat_id]) > self._limit:
            self._data[chat_id] = self._data[chat_id][-self._limit :]

    def get(self, chat_id: int) -> List[ChatMessage]:
        return self._data.get(chat_id, [])

    def get_dicts(self, chat_id: int) -> List[dict]:
        return [m.to_dict() for m in self.get(chat_id)]

    def clear(self, chat_id: int):
        self._data.pop(chat_id, None)


class ModelManager:
    def __init__(self, default: str):
        self._default = default
        self._data: Dict[int, str] = {}

    def get(self, chat_id: int) -> str:
        return self._data.get(chat_id, self._default)

    def set(self, chat_id: int, model: str):
        self._data[chat_id] = model
