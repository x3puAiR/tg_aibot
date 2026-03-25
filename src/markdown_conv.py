from __future__ import annotations

from telegramify_markdown import markdownify
from telegram.constants import ParseMode

_MAX_LEN = 4000


def md_to_chunks(text: str) -> list[tuple[str, str]]:
    """Convert markdown to (MarkdownV2_text, parse_mode) chunks within Telegram's limit.

    Splits raw markdown first so that no MarkdownV2 entity (e.g. a code fence)
    is ever cut across chunk boundaries.
    """
    raw_blocks = _split_raw_blocks(text)
    result: list[tuple[str, str]] = []
    pending = ""

    for block in raw_blocks:
        candidate = pending + "\n\n" + block if pending else block
        if len(markdownify(candidate)) <= _MAX_LEN:
            pending = candidate
        else:
            if pending:
                result.append((markdownify(pending), ParseMode.MARKDOWN_V2))
            converted = markdownify(block)
            if len(converted) > _MAX_LEN:
                for part in _split_oversized_block(block, converted):
                    result.append((part, ParseMode.MARKDOWN_V2))
                pending = ""
            else:
                pending = block

    if pending:
        result.append((markdownify(pending), ParseMode.MARKDOWN_V2))

    return result or [(markdownify(text), ParseMode.MARKDOWN_V2)]


def md_preview(text: str) -> tuple[str, None]:
    """Return plain text preview for streaming (no parse_mode).

    Applying MarkdownV2 to partial/incomplete markdown mid-stream is
    unreliable — plain text is safer for live previews.
    """
    return text[-_MAX_LEN:], None


def _split_raw_blocks(text: str) -> list[str]:
    """Split raw markdown at blank lines, never inside a fenced code block."""
    blocks: list[str] = []
    current: list[str] = []
    in_fence = False

    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            current.append(line)
        elif not in_fence and not line.strip():
            if current:
                blocks.append("\n".join(current))
                current = []
        else:
            current.append(line)

    if current:
        blocks.append("\n".join(current))

    return [b for b in blocks if b.strip()]


def _split_oversized_block(raw: str, converted: str) -> list[str]:
    """Split a single converted block that exceeds _MAX_LEN.

    For fenced code blocks: splits at line boundaries, re-wrapping each piece
    in the same fence so every chunk is a valid, self-contained snippet.
    For all other blocks: falls back to word-boundary hard-split.
    """
    lines = raw.strip().splitlines()
    if len(lines) >= 3:
        first = lines[0].lstrip()
        last = lines[-1].strip()
        for fence in ("```", "~~~"):
            if first.startswith(fence) and last.startswith(fence):
                lang = first[len(fence):].strip()
                open_tag = f"{fence}{lang}"
                body_lines = lines[1:-1]
                overhead = len(markdownify(f"{open_tag}\n.\n{fence}")) - 1
                budget = _MAX_LEN - overhead
                parts: list[str] = []
                chunk: list[str] = []
                chunk_len = 0
                for ln in body_lines:
                    ln_len = len(ln) + 1  # +1 for newline
                    if chunk and chunk_len + ln_len > budget:
                        block = f"{open_tag}\n" + "\n".join(chunk) + f"\n{fence}"
                        parts.append(markdownify(block))
                        chunk = [ln]
                        chunk_len = ln_len
                    else:
                        chunk.append(ln)
                        chunk_len += ln_len
                if chunk:
                    block = f"{open_tag}\n" + "\n".join(chunk) + f"\n{fence}"
                    parts.append(markdownify(block))
                return parts or _hard_split(converted)

    return _hard_split(converted)


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
