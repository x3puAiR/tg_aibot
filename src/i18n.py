from __future__ import annotations

from telegram import User

_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        # Help
        "help": (
            "Commands:\n"
            "/provider — set provider base URL\n"
            "/apikey — set provider API key\n"
            "/model — set model by name (e.g. /model gpt-4o-mini)\n"
            "/modellist — list all models from provider (tap to select)\n\n"
            "Session management:\n"
            "/new — start a new session\n"
            "/resume — resume a previous session\n"
            "/clear — discard current session and start fresh\n"
            "/del — delete a session\n\n"
            "Send any message to chat with the model."
        ),
        # Provider
        "provider_updated": "Provider URL updated.",
        "provider_current": "Current provider: {url}\nTo change: /provider <url>",
        "provider_not_set": "No provider set.\nUsage: /provider <url>\nExample: /provider https://api.openai.com",
        # API key
        "apikey_updated": "API key updated.",
        "apikey_current": "Current API key: {masked}\nTo change: /apikey <key>",
        "apikey_not_set": "No API key set.\nUsage: /apikey <key>",
        # Model
        "model_updated": "Model set to {model}.",
        "model_current": "Current model: {model}\nTo change: /model <name>\nExample: /model gpt-4o-mini",
        "model_not_set": "No model set.\nUsage: /model <name>\nExample: /model gpt-4o-mini",
        # Model list
        "modellist_no_provider": "No provider set. Use /provider to set your API base URL first.",
        "modellist_fetch_failed": "Failed to fetch models: {error}",
        "modellist_no_match": 'No models matching "{pattern}".',
        "modellist_empty": "Provider returned no models.",
        "modellist_header_filtered": 'Models matching "{pattern}" ({total}):',
        "modellist_header": "Available models ({total}):",
        "modellist_expired": "Model list expired. Run /modellist again.",
        # Model list nav buttons
        "btn_prev": "← Prev",
        "btn_next": "Next →",
        # Session
        "session_new": "New session started (#{id}). Send a message to begin.",
        "session_cleared": "Session cleared. New session started (#{id}).",
        "session_none": "No sessions found. Send a message to start one.",
        "session_choose_resume": "Choose a session to resume:",
        "session_none_to_delete": "No sessions to delete.",
        "session_choose_delete": "Choose a session to delete:",
        "session_resumed": 'Resumed: "{title}"',
        "session_confirm_delete": 'Delete session "{title}"?',
        "session_deleted": 'Deleted: "{title}"',
        "session_cancelled": "Cancelled.",
        "session_not_found": "Session not found.",
        # Session delete confirm buttons
        "btn_yes_delete": "Yes, delete",
        "btn_cancel": "Cancel",
        # Date labels (used in session list)
        "date_today": "today",
        "date_yesterday": "yesterday",
        # Chat errors
        "chat_no_provider": (
            "No provider set.\n"
            "Use /provider to set your API base URL.\n"
            "Example: /provider https://api.openai.com"
        ),
        "chat_no_model": (
            "No model set.\n"
            "Use /model <name> to set your model.\n"
            "Example: /model gpt-4o-mini"
        ),
        "chat_invalid_url": (
            "Invalid provider URL. Use /provider to set a valid URL.\n"
            "Example: /provider https://api.openai.com"
        ),
        "chat_connect_error": "Cannot connect to provider. Check your URL with /provider.\n({error})",
        "chat_request_failed": "Request failed: {error}",
        # Token footer
        "token_footer": '▸ "{title}" · {tokens} tokens',
        # Misc
        "empty_response": "(empty response)",
    },

    "zh": {
        # Help
        "help": (
            "指令列表：\n"
            "/provider — 設定 API 服務商網址\n"
            "/apikey — 設定 API 金鑰\n"
            "/model — 設定模型名稱（例：/model gpt-4o-mini）\n"
            "/modellist — 列出服務商所有模型（點選即可套用）\n\n"
            "對話管理：\n"
            "/new — 開始新對話\n"
            "/resume — 切換至之前的對話\n"
            "/clear — 清除目前對話並重新開始\n"
            "/del — 刪除對話\n\n"
            "直接發送訊息即可開始與模型對話。"
        ),
        # Provider
        "provider_updated": "服務商網址已更新。",
        "provider_current": "目前服務商：{url}\n如需更改：/provider <url>",
        "provider_not_set": "尚未設定服務商。\n用法：/provider <url>\n範例：/provider https://api.openai.com",
        # API key
        "apikey_updated": "API 金鑰已更新。",
        "apikey_current": "目前 API 金鑰：{masked}\n如需更改：/apikey <key>",
        "apikey_not_set": "尚未設定 API 金鑰。\n用法：/apikey <key>",
        # Model
        "model_updated": "模型已設定為 {model}。",
        "model_current": "目前模型：{model}\n如需更改：/model <name>\n範例：/model gpt-4o-mini",
        "model_not_set": "尚未設定模型。\n用法：/model <name>\n範例：/model gpt-4o-mini",
        # Model list
        "modellist_no_provider": "尚未設定服務商，請先使用 /provider 設定 API 網址。",
        "modellist_fetch_failed": "取得模型列表失敗：{error}",
        "modellist_no_match": '找不到符合「{pattern}」的模型。',
        "modellist_empty": "服務商未回傳任何模型。",
        "modellist_header_filtered": '符合「{pattern}」的模型（共 {total} 個）：',
        "modellist_header": "可用模型（共 {total} 個）：",
        "modellist_expired": "模型列表已過期，請重新執行 /modellist。",
        # Model list nav buttons
        "btn_prev": "← 上一頁",
        "btn_next": "下一頁 →",
        # Session
        "session_new": "新對話已建立（#{id}），請發送訊息開始。",
        "session_cleared": "目前對話已清除，新對話已建立（#{id}）。",
        "session_none": "找不到任何對話，請直接發送訊息開始新對話。",
        "session_choose_resume": "請選擇要繼續的對話：",
        "session_none_to_delete": "沒有可刪除的對話。",
        "session_choose_delete": "請選擇要刪除的對話：",
        "session_resumed": '已切換至：「{title}」',
        "session_confirm_delete": '確定要刪除對話「{title}」嗎？',
        "session_deleted": '已刪除：「{title}」',
        "session_cancelled": "已取消。",
        "session_not_found": "找不到該對話。",
        # Session delete confirm buttons
        "btn_yes_delete": "確認刪除",
        "btn_cancel": "取消",
        # Date labels
        "date_today": "今天",
        "date_yesterday": "昨天",
        # Chat errors
        "chat_no_provider": (
            "尚未設定服務商。\n"
            "請使用 /provider 設定 API 網址。\n"
            "範例：/provider https://api.openai.com"
        ),
        "chat_no_model": (
            "尚未設定模型。\n"
            "請使用 /model <name> 設定模型。\n"
            "範例：/model gpt-4o-mini"
        ),
        "chat_invalid_url": (
            "服務商網址無效，請使用 /provider 重新設定。\n"
            "範例：/provider https://api.openai.com"
        ),
        "chat_connect_error": "無法連線至服務商，請確認網址是否正確。\n（{error}）",
        "chat_request_failed": "請求失敗：{error}",
        # Token footer
        "token_footer": '▸「{title}」· {tokens} tokens',
        # Misc
        "empty_response": "（無回應）",
    },
}


def get_lang(user: User) -> str:
    """Detect display language from the user's Telegram language_code."""
    lc = (getattr(user, "language_code", None) or "en").lower()
    if lc.startswith("zh"):
        return "zh"
    return "en"


def t(key: str, lang: str, **kwargs: object) -> str:
    """Look up a translated string and interpolate any keyword arguments."""
    strings = _STRINGS.get(lang, _STRINGS["en"])
    template = strings.get(key) or _STRINGS["en"].get(key, key)
    return template.format(**kwargs) if kwargs else template
