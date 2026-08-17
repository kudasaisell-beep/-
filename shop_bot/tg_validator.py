import asyncio
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from config import TELEGRAM_API_ID, TELEGRAM_API_HASH

logger = logging.getLogger(__name__)


async def validate_account(session_string: str, phone: str = None) -> dict:
    """
    Проверяет валидность сессии Telegram.
    Возвращает {"ok": True} или {"ok": False, "error": str}
    """
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        logger.warning("Telegram API credentials not set, skipping validation")
        return {"ok": True}

    client = TelegramClient(StringSession(session_string), TELEGRAM_API_ID, TELEGRAM_API_HASH)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return {"ok": False, "error": "Session not authorized"}

        me = await client.get_me()
        if me is None:
            await client.disconnect()
            return {"ok": False, "error": "Cannot get user info"}

        # Проверяем спамблок (ограничение на отправку сообщений)
        try:
            await client.send_message("@SpamBot", "/start")
        except Exception as e:
            err_str = str(e).lower()
            if "limit" in err_str or "restricted" in err_str or "banned" in err_str:
                await client.disconnect()
                return {"ok": False, "error": f"Account restricted: {e}"}

        await client.disconnect()
        return {"ok": True}
    except Exception as e:
        logger.error(f"Validation error: {e}")
        try:
            await client.disconnect()
        except Exception:
            pass
        return {"ok": False, "error": str(e)}
