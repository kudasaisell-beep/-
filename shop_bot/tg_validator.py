import asyncio
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from config import TELEGRAM_API_ID, TELEGRAM_API_HASH

logger = logging.getLogger(__name__)

async def validate_account(session_string: str, phone: str = None) -> dict:
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        logger.warning("Telegram API credentials not set, skipping validation")
        return {"ok": True}

    client = None
    try:
        client = TelegramClient(
            StringSession(session_string),
            TELEGRAM_API_ID,
            TELEGRAM_API_HASH
        )
        await client.connect()
        if not await client.is_user_authorized():
            return {"ok": False, "error": "Session not authorized"}

        me = await client.get_me()
        if me is None:
            return {"ok": False, "error": "Cannot get user info"}

        try:
            await client.send_message("@SpamBot", "/start")
        except Exception as e:
            err = str(e).lower()
            if any(x in err for x in ("limit", "restricted", "banned")):
                return {"ok": False, "error": "Account restricted"}

        return {"ok": True}
    except Exception as e:
        logger.error(f"Validation error for phone {phone or 'hidden'}: {type(e).__name__}")
        return {"ok": False, "error": "Validation failed"}
    finally:
        if client:
            try:
                await client.disconnect()
            except Exception:
                pass
