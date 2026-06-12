import json
import logging
from typing import AsyncIterator, List

import httpx

from .storage import ChatMessage

logger = logging.getLogger(__name__)


class FreeDeepseekError(Exception):
    def __init__(self, status: int, detail: str = ""):
        self.status = status
        self.detail = detail
        super().__init__(f"API error {status}: {detail}")


class FreeDeepseekClient:
    def __init__(self, api_url: str, timeout: float = 120.0, connect_timeout: float = 10.0):
        url = api_url.rstrip("/")
        self._chat_url = f"{url}/chat/completions"
        self._api_root = url.rstrip("/v1").rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=connect_timeout),
            follow_redirects=True,
        )

    async def close(self):
        await self._client.aclose()

    async def stream_chat(
        self, session_id: str, model: str, messages: List[ChatMessage]
    ) -> AsyncIterator[str]:
        body = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
        }
        headers = {"x-agent-session": session_id}

        async with self._client.stream("POST", self._chat_url, json=body, headers=headers) as resp:
            if resp.status_code != 200:
                text = await resp.aread()
                detail = text.decode(errors="replace")[:500]
                logger.error("API error %s: %s", resp.status_code, detail)
                raise FreeDeepseekError(resp.status_code, detail)

            async for line in resp.aiter_lines():
                line = line.strip()
                if not line.startswith("data: "):
                    continue

                payload = line[6:]
                if payload == "[DONE]":
                    break

                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    logger.warning("Failed to parse SSE chunk: %s", payload[:200])
                    continue

                for choice in chunk.get("choices", []):
                    delta = choice.get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield content

    async def reset_session(self, session_id: str) -> bool:
        url = f"{self._api_root}/reset-session?agent={session_id}"
        resp = await self._client.post(url)
        if resp.status_code == 200:
            logger.info("Session reset: %s", session_id)
            return True
        logger.warning("Session reset failed %s: %s", session_id, resp.status_code)
        return False
