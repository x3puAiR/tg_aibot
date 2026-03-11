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

Then just send any message to start chatting.

## Core Features

**Streaming responses** — Uses Telegram's `sendMessageDraft` API to show the response as it generates, word by word. Falls back to message editing if unavailable.

**Session management** — Conversation history is preserved per session. Each session is auto-titled from the first message.
- `/new` — start a fresh session
- `/resume` — switch to a previous session
- `/clear` — wipe current session and start over
- `/del` — delete a session

**Token tracking** — After every response, a footer shows the cumulative token usage for the current session: `▸ "session title" · 1,234 tokens`

**Per-user config** — Provider URL, API key, and model are stored per user in SQLite. Works with any OpenAI-compatible endpoint (OpenAI, Anthropic via proxy, local Ollama, etc.).
