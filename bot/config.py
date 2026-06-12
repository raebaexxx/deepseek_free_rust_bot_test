from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    telegram_token: str = os.getenv("TELOXIDE_TOKEN", "")
    api_url: str = os.getenv("DEEPSEEK_API_URL", "http://localhost:9655/v1")
    default_model: str = os.getenv("DEFAULT_MODEL", "deepseek-chat")

    history_limit: int = 20
    edit_interval: float = 0.4
    max_message_length: int = 100_000

    api_timeout: float = 120.0
    api_connect_timeout: float = 10.0
