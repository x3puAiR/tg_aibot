import os


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
STREAM_UPDATE_INTERVAL_SEC = float(os.getenv("STREAM_UPDATE_INTERVAL_SEC", "0.6"))
DB_PATH = "data/bot.db"
