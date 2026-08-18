import os
from dotenv import load_dotenv

_dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=_dotenv_path, override=True)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip().strip('"').strip("'")
LZT_TOKEN = os.getenv("LZT_TOKEN", "").strip().strip('"').strip("'")
ADMIN_ID_STR = os.getenv("ADMIN_ID", "").strip()
ADMIN_CHAT_ID_STR = os.getenv("ADMIN_CHAT_ID", "").strip()

ADMIN_IDS = []
if ADMIN_ID_STR:
    try:
        ADMIN_IDS = [int(x.strip()) for x in ADMIN_ID_STR.split(",") if x.strip()]
    except ValueError:
        pass

ADMIN_CHAT_ID = None
if ADMIN_CHAT_ID_STR:
    try:
        ADMIN_CHAT_ID = int(ADMIN_CHAT_ID_STR)
    except ValueError:
        pass

TOPIC_PURCHASES = None
try:
    TOPIC_PURCHASES = int(os.getenv("TOPIC_PURCHASES", ""))
except ValueError:
    pass

TOPIC_TOPUPS = None
try:
    TOPIC_TOPUPS = int(os.getenv("TOPIC_TOPUPS", ""))
except ValueError:
    pass

TOPIC_MONITORING = None
try:
    TOPIC_MONITORING = int(os.getenv("TOPIC_MONITORING", ""))
except ValueError:
    pass

_BOT_TOKEN_VALID = True
if not BOT_TOKEN:
    print("⚠️ WARNING: BOT_TOKEN empty!")
    _BOT_TOKEN_VALID = False
elif not BOT_TOKEN.count(":") == 1 or len(BOT_TOKEN) < 20:
    print(f"⚠️ WARNING: BOT_TOKEN looks invalid")
    _BOT_TOKEN_VALID = False

print(f"BOT_TOKEN loaded: {BOT_TOKEN[:15]}...")
print(f"ADMIN_IDS: {ADMIN_IDS}")
print(f"ADMIN_CHAT_ID: {ADMIN_CHAT_ID}")
print(f"TOPICS: purchases={TOPIC_PURCHASES}, topups={TOPIC_TOPUPS}, monitoring={TOPIC_MONITORING}")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://shop:shop@localhost:5432/shop")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8080"))
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

MIN_LZT_BALANCE = float(os.getenv("MIN_LZT_BALANCE", "1000"))
purchases_paused = False

TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")

LZT_RATE_LIMIT = float(os.getenv("LZT_RATE_LIMIT", "0.2"))
USER_BUY_COOLDOWN = int(os.getenv("USER_BUY_COOLDOWN", "10"))

BACKUP_BOT_TOKENS = []
_backup_raw = os.getenv("BACKUP_BOT_TOKENS", "").strip()
if _backup_raw:
    BACKUP_BOT_TOKENS = [t.strip() for t in _backup_raw.split(",") if t.strip()]

SENTRY_DSN = os.getenv("SENTRY_DSN", "")
CF_MODE = os.getenv("CF_MODE", "false").lower() == "true"
