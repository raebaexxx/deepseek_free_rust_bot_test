import asyncio
import json
import logging
import os
import subprocess
from typing import AsyncIterator, Optional

import httpx

logger = logging.getLogger(__name__)

SOLVE_POW_JS = os.path.join(os.path.dirname(__file__), "solve_pow.js")


def _find_auth_file() -> Optional[str]:
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "deepseek-auth.json"),
        os.path.join(os.path.dirname(__file__), "..", "FreeDeepseekAPI", "deepseek-auth.json"),
        os.environ.get("DEEPSEEK_AUTH_PATH", ""),
    ]
    for p in candidates:
        if p and os.path.isfile(p):
            return os.path.realpath(p)
    return None


def load_auth(auth_path: Optional[str] = None) -> dict:
    path = auth_path or _find_auth_file()
    if not path:
        raise FileNotFoundError(
            "deepseek-auth.json not found. Set DEEPSEEK_AUTH_PATH or place it "
            "next to bot/ or in FreeDeepseekAPI/"
        )
    with open(path) as f:
        return json.load(f)


def _build_headers(auth: dict) -> dict:
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "x-client-platform": "web",
        "x-client-version": "2.0.0",
        "x-client-locale": "ru",
        "x-client-timezone-offset": "14400",
        "x-app-version": "2.0.0",
        "Authorization": f"Bearer {auth.get('token', '')}",
        "x-hif-dliq": auth.get("hif_dliq", ""),
        "x-hif-leim": auth.get("hif_leim", ""),
        "Origin": "https://chat.deepseek.com",
        "Referer": "https://chat.deepseek.com/",
        "Cookie": auth.get("cookie", ""),
    }


async def _solve_pow(challenge: dict, wasm_url: str) -> int:
    payload = json.dumps({"challenge": challenge, "wasmUrl": wasm_url})
    proc = await asyncio.create_subprocess_exec(
        "node", SOLVE_POW_JS,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate(payload.encode())
    if proc.returncode != 0:
        raise RuntimeError(f"PoW solver failed: {stderr.decode(errors='replace')}")
    return int(stdout.decode().strip())


async def upload_file(
    file_bytes: bytes,
    filename: str,
    mime: str,
    auth: dict,
    upload_url: Optional[str] = None,
) -> str:
    url = upload_url or "https://chat.deepseek.com/api/v0/file/upload"
    headers = _build_headers(auth)

    async with httpx.AsyncClient() as client:
        files = {"file": (filename, file_bytes, mime)}
        resp = await client.post(url, headers=headers, files=files, timeout=120)

    if resp.status_code != 200:
        logger.warning("File upload failed (%s): %s", resp.status_code, resp.text[:200])
        raise RuntimeError(f"Upload failed: HTTP {resp.status_code}")

    data = resp.json()
    file_id = (
        data.get("data", {}).get("biz_data", {}).get("id")
        or data.get("data", {}).get("biz_data", {}).get("file_id")
        or data.get("id")
    )
    if not file_id:
        logger.warning("No file id in response: %s", resp.text[:300])
        raise RuntimeError("Could not parse file ID from upload response")
    return file_id


async def stream_chat(
    prompt: str,
    auth: dict,
    file_ids: Optional[list[str]] = None,
    model_type: str = "default",
    thinking_enabled: bool = False,
    search_enabled: bool = False,
) -> AsyncIterator[str]:
    headers = _build_headers(auth)
    headers["Content-Type"] = "application/json"

    pow_resp = await _send_request(
        "POST",
        "https://chat.deepseek.com/api/v0/chat/create_pow_challenge",
        headers,
        {"target_path": "/api/v0/chat/completion"},
    )
    pow_data = pow_resp.json()
    challenge = pow_data["data"]["biz_data"]["challenge"]
    wasm_url = auth.get("wasmUrl", "https://fe-static.deepseek.com/chat/static/sha3_wasm_bg.7b9ca65ddd.wasm")
    answer = await _solve_pow(challenge, wasm_url)

    sess_resp = await _send_request(
        "POST",
        "https://chat.deepseek.com/api/v0/chat_session/create",
        headers,
        {},
    )
    sess_data = sess_resp.json()
    session_id = (
        sess_data.get("data", {}).get("biz_data", {}).get("chat_session", {}).get("id")
        or sess_data.get("data", {}).get("biz_data", {}).get("id")
    )
    if not session_id:
        raise RuntimeError("Could not create chat session")

    pow_b64 = _b64encode_json({
        "algorithm": challenge["algorithm"],
        "challenge": challenge["challenge"],
        "salt": challenge["salt"],
        "answer": answer,
        "signature": challenge["signature"],
        "target_path": "/api/v0/chat/completion",
    })

    body = {
        "chat_session_id": session_id,
        "parent_message_id": None,
        "model_type": model_type,
        "prompt": prompt,
        "ref_file_ids": file_ids or [],
        "thinking_enabled": thinking_enabled,
        "search_enabled": search_enabled,
        "action": None,
        "preempt": False,
    }
    completion_headers = {**headers, "X-DS-PoW-Response": pow_b64}

    async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=30)) as client:
        async with client.stream(
            "POST",
            "https://chat.deepseek.com/api/v0/chat/completion",
            headers=completion_headers,
            json=body,
        ) as resp:
            if resp.status_code != 200:
                text = await resp.aread()
                raise RuntimeError(f"Completion failed: HTTP {resp.status_code} {text[:200]}")

            last_path = None
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if not payload:
                    continue
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if "p" in chunk:
                    last_path = chunk["p"]
                if last_path == "response/content" and "v" in chunk:
                    yield chunk["v"]


async def _send_request(method: str, url: str, headers: dict, json_body: dict) -> httpx.Response:
    async with httpx.AsyncClient() as client:
        resp = await client.request(method, url, headers=headers, json=json_body, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"{url} failed: HTTP {resp.status_code} {resp.text[:200]}")
    return resp


def _b64encode_json(data: dict) -> str:
    import base64
    return base64.b64encode(json.dumps(data, separators=(",", ":")).encode()).decode()
