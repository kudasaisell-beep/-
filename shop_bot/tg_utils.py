"""
Безопасные обёртки для ответов Telegram.

FIX 14: проверка длины сообщений (max 4096 символов Telegram).
FIX 19: обработка FloodWait с retry.
"""
import logging
import asyncio

from aiogram.types import CallbackQuery, Message
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter

logger = logging.getLogger(__name__)
TELEGRAM_MAX_MSG_LEN = 4096

async def safe_answer(callback: CallbackQuery, text: str = None, show_alert: bool = False) -> bool:
    try:
        await callback.answer(text=text, show_alert=show_alert)
        return True
    except TelegramBadRequest as e:
        err = str(e).lower()
        if "query is too old" in err or "query id is invalid" in err:
            logger.warning(f"Callback query expired: {e}")
        else:
            logger.warning(f"Failed to answer callback: {e}")
        return False
    except Exception as e:
        logger.warning(f"Failed to answer callback: {e}")
        return False

async def safe_edit(target, text: str, reply_markup=None, **kwargs) -> bool:
    message = target.message if isinstance(target, CallbackQuery) else target
    if message is None:
        return False
    text = _truncate_text(text)
    try:
        await message.edit_text(text, reply_markup=reply_markup, **kwargs)
        return True
    except TelegramBadRequest as e:
        err = str(e).lower()
        if "message is not modified" in err:
            return True
        try:
            await message.answer(text, reply_markup=reply_markup, **kwargs)
            return True
        except Exception as e2:
            logger.warning(f"Failed to edit/send message: {e2}")
            return False
    except Exception as e:
        logger.warning(f"Failed to edit message: {e}")
        return False

async def send_safe_message(bot_or_target, text: str, reply_markup=None, **kwargs):
    """Отправка сообщения с обработкой FloodWait и разбиением на части."""
    chunks = _split_text(text)
    last_msg = None
    for chunk in chunks:
        for attempt in range(5):
            try:
                if isinstance(bot_or_target, Message):
                    last_msg = await bot_or_target.answer(chunk, reply_markup=reply_markup if chunk is chunks[-1] else None, **kwargs)
                else:
                    last_msg = await bot_or_target.send_message(chat_id=kwargs.pop("chat_id", None) or bot_or_target.chat.id,
                                                                 text=chunk,
                                                                 reply_markup=reply_markup if chunk is chunks[-1] else None,
                                                                 **kwargs)
                break
            except TelegramRetryAfter as e:
                logger.warning(f"FloodWait: sleeping {e.retry_after}s")
                await asyncio.sleep(e.retry_after + 1)
            except Exception as e:
                logger.error(f"Send failed (attempt {attempt+1}/5): {e}")
                await asyncio.sleep(2 ** attempt)
    return last_msg

def _truncate_text(text: str, max_len: int = TELEGRAM_MAX_MSG_LEN - 10) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "

... (сообщение обрезано)"

def _split_text(text: str, max_len: int = TELEGRAM_MAX_MSG_LEN - 100) -> list:
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        split_at = text.rfind("
", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("
")
    return chunks
