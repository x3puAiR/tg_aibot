from __future__ import annotations

import asyncio
import json

import aiohttp


class ProviderError(RuntimeError):
    pass


def _provider_error(status: int, body: str) -> str:
    hints = {
        401: "API key rejected (401 Unauthorized). Check your key with /apikey.",
        403: "Access denied (403 Forbidden). Check your API key with /apikey.",
        404: "Endpoint not found (404). Check your provider URL with /provider and model name with /model.",
        422: "Invalid request (422 Unprocessable). Check your model name with /model.",
        429: "Rate limit reached (429). Your API quota may be exhausted.",
    }
    hint = hints.get(status, f"Provider error {status}.")
    body = body.strip()
    return f"{hint}\n\nAPI response:\n{body}" if body else hint


def _completion_url(base: str) -> str:
    base = base.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


class ChatStream:
    """Async-iterable streaming chat request.

    Yields text content chunks. After the async-for loop completes,
    ``usage`` may contain token counts from the API (prompt_tokens,
    completion_tokens, total_tokens), or None if the provider omits it.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        base_url: str,
        api_key: str | None,
        model: str,
        messages: list[dict],
        timeout_sec: float = 120.0,
    ) -> None:
        self._session = session
        self._url = _completion_url(base_url)
        self._headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"
        self._payload: dict = {
            "model": model,
            "stream": True,
            "messages": messages,
        }
        self._timeout_sec = timeout_sec
        self.usage: dict | None = None

    def __aiter__(self):
        return self._stream()

    async def _stream(self):
        try:
            async with self._session.post(
                self._url,
                headers=self._headers,
                json=self._payload,
                timeout=aiohttp.ClientTimeout(total=self._timeout_sec),
            ) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    raise ProviderError(_provider_error(resp.status, body))

                async for raw in resp.content:
                    line = raw.decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue
                    for chunk in line.split("\n"):
                        chunk = chunk.strip()
                        if not chunk:
                            continue
                        if chunk.startswith("data:"):
                            data = chunk[len("data:"):].strip()
                        else:
                            data = chunk

                        if data == "[DONE]":
                            return
                        try:
                            obj = json.loads(data)
                        except json.JSONDecodeError:
                            continue

                        # Capture usage if the provider includes it
                        if obj.get("usage"):
                            self.usage = obj["usage"]

                        choices = obj.get("choices") or []
                        if choices:
                            delta = (
                                choices[0].get("delta")
                                or choices[0].get("message")
                                or {}
                            )
                            content = delta.get("content")
                            if content:
                                yield content
                await asyncio.sleep(0)
        except asyncio.TimeoutError as exc:
            raise ProviderError("Provider request timed out") from exc


async def chat_once(
    session: aiohttp.ClientSession,
    *,
    base_url: str,
    api_key: str | None,
    model: str,
    messages: list[dict],
    timeout_sec: float = 60.0,
) -> tuple[str, dict | None]:
    """Non-streaming chat. Returns (content, usage_dict_or_None)."""
    url = _completion_url(base_url)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "stream": False,
        "messages": messages,
    }

    try:
        async with session.post(
            url,
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=timeout_sec),
        ) as resp:
            if resp.status >= 400:
                body = await resp.text()
                raise ProviderError(_provider_error(resp.status, body))
            data = await resp.json()
    except asyncio.TimeoutError as exc:
        raise ProviderError("Provider request timed out") from exc

    choices = data.get("choices") or [{}]
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not content:
        raise ProviderError("Provider returned empty response")
    usage = data.get("usage") or None
    return content, usage
