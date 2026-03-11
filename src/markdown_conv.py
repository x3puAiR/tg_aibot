from __future__ import annotations

from telegramify_markdown import convert, split_entities as _split_entities
from telegram import MessageEntity

# Safe limit in UTF-16 code units (Telegram max is 4096)
_MAX_UTF16 = 4000


def md_to_chunks(text: str) -> list[tuple[str, list[MessageEntity]]]:
    """Convert standard markdown to a list of (plain_text, entities) chunks.

    Each chunk fits within Telegram's message length limit.
    Entity offsets are recalculated per-chunk by split_entities.
    """
    plain, entities = convert(text)
    if not plain:
        return [("(empty response)", [])]
    chunks = _split_entities(plain, entities, _MAX_UTF16)
    return chunks if chunks else [(plain[:_MAX_UTF16], [])]


def md_preview(text: str) -> tuple[str, list[MessageEntity]]:
    """Convert a markdown snippet for a live streaming preview.

    Takes the last ~4000 characters so the preview stays within limits
    even when the buffer is large. Conversion is best-effort on partial text.
    """
    snippet = text[-4000:]
    plain, entities = convert(snippet)
    # Clamp in case conversion expanded the text somehow
    if len(plain) > _MAX_UTF16:
        plain = plain[:_MAX_UTF16]
        entities = [e for e in entities if e.offset + e.length <= _MAX_UTF16]
    return plain, entities
