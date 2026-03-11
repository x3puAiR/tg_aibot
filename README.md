# tg-aibot

A Telegram bot that connects to any OpenAI-compatible API and streams responses back in real time. Each user brings their own API credentials — no shared keys.

## Quick Start

**1. Clone and configure**
```bash
git clone <repo-url>
cd tg-aibot
cp .env.example .env
```

Edit `.env` and set your bot token:
```env
TELEGRAM_BOT_TOKEN=your_token_here
```

Get a token from [@BotFather](https://t.me/BotFather) on Telegram if you don't have one.

**2. Run**
```bash
docker compose up -d
docker compose logs -f   # watch logs
```

## First-time Setup (in Telegram)

Each user must configure their own API before chatting:

```
/provider https://api.openai.com
/apikey   sk-...
/model    gpt-4o-mini
```

Or use `/modellist` to browse all models from your provider and tap one to select it.

Then just send any message to start chatting.

## Commands

| Command | Description |
|---|---|
| `/provider [url]` | Set provider base URL (shows current if no argument) |
| `/apikey [key]` | Set provider API key (shows masked current if no argument) |
| `/model <name>` | Set model by name |
| `/modellist [pattern]` | List all available models; tap one to select it |
| `/new` | Start a new chat session |
| `/resume` | Switch to a previous session |
| `/clear` | Discard current session and start fresh |
| `/del` | Delete a session |
| `/help` | Show help |

## Core Features

**Streaming responses** — Uses Telegram's `sendMessageDraft` API to show the response as it generates, word by word. Falls back to message editing if unavailable.

**Markdown rendering** — AI responses are rendered with proper Telegram formatting: bold, italic, inline code, code blocks with language hints, strikethrough, and more.

**Model browser** — `/modellist` fetches available models from your provider's `/v1/models` endpoint and displays them as a tappable list. Use `/modellist <pattern>` to filter (e.g. `/modellist gpt-4`). The currently active model is marked with ★.

**Session management** — Conversation history is preserved per session. Each session is auto-titled from the first message.

**Token tracking** — After every response, a footer shows the cumulative token usage for the current session: `▸ "session title" · 1,234 tokens`

**Per-user config** — Provider URL, API key, and model are stored per user in SQLite. Works with any OpenAI-compatible endpoint (OpenAI, Anthropic via proxy, local Ollama, etc.).
