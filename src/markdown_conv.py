from __future__ import annotations

from telegramify_markdown import markdownify
from telegram.constants import ParseMode

_MAX_LEN = 4000


def md_to_chunks(text: str) -> list[tuple[str, str]]:
    """Convert standard markdown to (MarkdownV2_text, parse_mode) chunks.

    Each chunk is within Telegram's ~4000 char limit, split at paragraph
    boundaries to avoid cutting inside formatting entities.
    """
    mdv2 = markdownify(text)
    if len(mdv2) <= _MAX_LEN:
        return [(mdv2, ParseMode.MARKDOWN_V2)]
    return [
        (chunk, ParseMode.MARKDOWN_V2)
        for chunk in _split_paragraphs(mdv2)
    ]


def md_preview(text: str) -> tuple[str, None]:
    """Return plain text preview for streaming (no parse_mode).

    Applying MarkdownV2 to partial/incomplete markdown mid-stream is
    unreliable — plain text is safer for live previews.
    """
    return text[-_MAX_LEN:], None


def _hard_split(text: str) -> list[str]:
    """Split text that exceeds _MAX_LEN at word boundaries."""
    result = []
    while len(text) > _MAX_LEN:
        split_at = text.rfind(" ", 0, _MAX_LEN)
        if split_at == -1:
            split_at = _MAX_LEN
        result.append(text[:split_at])
        text = text[split_at:].lstrip()
    if text:
        result.append(text)
    return result


def _split_paragraphs(text: str) -> list[str]:
    """Split MarkdownV2 text at paragraph boundaries, respecting the char limit."""
    chunks: list[str] = []
    current = ""
    for para in text.split("\n\n"):
        seg = para + "\n\n"
        if len(seg) > _MAX_LEN:
            if current:
                chunks.append(current.rstrip())
                current = ""
            chunks.extend(_hard_split(seg.rstrip()))
        elif len(current) + len(seg) > _MAX_LEN:
            if current:
                chunks.append(current.rstrip())
            current = seg
        else:
            current += seg
    if current.strip():
        chunks.append(current.rstrip())
    return chunks or _hard_split(text)
