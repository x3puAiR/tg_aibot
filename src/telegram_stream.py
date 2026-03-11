from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import aiohttp
from telegram import Bot

from markdown_conv import md_preview, md_to_chunks


@dataclass
class StreamTarget:
    chat_id: int
    message_thread_id: int | None
    # sendMessageDraft is available to all bots since Bot API 9.5 (March 2026).
    # Set to False only to force the edit_message_text fallback path.
    can_use_draft: bool = True


def _now_ms() -> int:
    return int(time.time() * 1000)


def _make_draft_id() -> int:
    return _now_ms() % 2_000_000_000 or 1


class TelegramStreamer:
    def __init__(self, *, bot: Bot, token: str, session: aiohttp.ClientSession) -> None:
        self._bot = bot
        self._token = token
        self._session = session

    async def _send_message_draft(
        self,
        *,
        target: StreamTarget,
        draft_id: int,
        plain: str,
        entities: list,
    ) -> None:
        url = f"https://api.telegram.org/bot{self._token}/sendMessageDraft"
        payload: dict[str, object] = {
            "chat_id": target.chat_id,
            "draft_id": draft_id,
            "text": plain,
            "entities": [e.to_dict() for e in entities],
        }
        if target.message_thread_id is not None:
            payload["message_thread_id"] = target.message_thread_id

        async with self._session.post(
            url, json=payload, timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            if resp.status >= 400:
                body = await resp.text()
                raise RuntimeError(f"sendMessageDraft failed: {resp.status} {body}")

    async def stream_text(
        self,
        *,
        target: StreamTarget,
        text_stream,
        update_interval: float,
    ) -> str:
        """Stream text to Telegram. Returns the final raw (unconverted) text."""
        text_buffer = ""
        last_update = 0.0
        draft_id = _make_draft_id() if target.can_use_draft else None
        message = None

        async for piece in text_stream:
            text_buffer += piece
            now = time.time()
            if now - last_update < update_interval:
                continue
            last_update = now

            # Convert current buffer to plain+entities once; reuse for both paths
            preview_plain, preview_ents = md_preview(text_buffer)

            if target.can_use_draft and draft_id is not None:
                try:
                    await self._send_message_draft(
                        target=target,
                        draft_id=draft_id,
                        plain=preview_plain,
                        entities=preview_ents,
                    )
                except Exception:
                    # Fall back to edit_message_text for the rest of the stream
                    target = StreamTarget(
                        chat_id=target.chat_id,
                        message_thread_id=target.message_thread_id,
                        can_use_draft=False,
                    )
                    draft_id = None

            if not target.can_use_draft:
                if message is None:
                    message = await self._bot.send_message(
                        chat_id=target.chat_id,
                        message_thread_id=target.message_thread_id,
                        text="…",
                    )
                await self._bot.edit_message_text(
                    chat_id=target.chat_id,
                    message_id=message.message_id,
                    text=preview_plain,
                    entities=preview_ents,
                )
            await asyncio.sleep(0)

        # ── Finalize ────────────────────────────────────────────────
        final_text = text_buffer.strip() or "(empty response)"
        final_chunks = md_to_chunks(final_text)

        if target.can_use_draft and draft_id is not None:
            # Draft was shown during streaming; send the permanent message(s).
            # The draft disappears automatically when the final sendMessage arrives.
            for plain, ents in final_chunks:
                await self._bot.send_message(
                    chat_id=target.chat_id,
                    message_thread_id=target.message_thread_id,
                    text=plain,
                    entities=ents,
                )
        else:
            if message is None:
                # Response came back without any interim updates (very fast)
                for plain, ents in final_chunks:
                    await self._bot.send_message(
                        chat_id=target.chat_id,
                        message_thread_id=target.message_thread_id,
                        text=plain,
                        entities=ents,
                    )
            else:
                first_plain, first_ents = final_chunks[0]
                await self._bot.edit_message_text(
                    chat_id=target.chat_id,
                    message_id=message.message_id,
                    text=first_plain,
                    entities=first_ents,
                )
                for plain, ents in final_chunks[1:]:
                    await self._bot.send_message(
                        chat_id=target.chat_id,
                        message_thread_id=target.message_thread_id,
                        text=plain,
                        entities=ents,
                    )

        return final_text  # raw AI text, not converted — for DB persistence
