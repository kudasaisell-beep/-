"""
Безопасные обёртки для ответов Telegram.

Главная причина ошибки «Bad Request: query is too old and response timeout
expired or query ID is invalid» — бот отвечает на callback query ПОСЛЕ долгих
операций (поиск/выкуп лотов на LZT занимает 3–60+ секунд), а Telegram требует
answerCallbackQuery в течение ~15 секунд после нажатия кнопки.

Правила:
1. В хендлерах с долгими операциями вызывай safe_answer() СРАЗУ в начале.
2. Все остальные ответы — только через safe_answer()/safe_edit(), они не
   роняют хендлер, если query протух или сообщение не изменилось.
"""
import logging

from aiogram.types import CallbackQuery, Message
from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger(__name__)


async def safe_answer(callback: CallbackQuery, text: str = None, show_alert: bool = False) -> bool:
    """
    Отвечает на callback query. Не падает, если query протух
    (>15 сек с момента нажатия) или ID уже недействителен.
    Возвращает True, если ответ доставлен.
    """
    try:
        await callback.answer(text=text, show_alert=show_alert)
        return True
    except TelegramBadRequest as e:
        err = str(e).lower()
        if "query is too old" in err or "query id is invalid" in err:
            logger.warning(f"Callback query expired (answered too late): {e}")
        else:
            logger.warning(f"Failed to answer callback: {e}")
        return False
    except Exception as e:
        logger.warning(f"Failed to answer callback: {e}")
        return False


async def safe_edit(target, text: str, reply_markup=None, **kwargs) -> bool:
    """
    Редактирует сообщение. Игнорирует «message is not modified»,
    при невозможности редактирования отправляет новое сообщение.
    target — CallbackQuery или Message.
    """
    message = target.message if isinstance(target, CallbackQuery) else target
    if message is None:
        return False
    try:
        await message.edit_text(text, reply_markup=reply_markup, **kwargs)
        return True
    except TelegramBadRequest as e:
        err = str(e).lower()
        if "message is not modified" in err:
            return True
        # Сообщение слишком старое/удалено — отправляем новое
        try:
            await message.answer(text, reply_markup=reply_markup, **kwargs)
            return True
        except Exception as e2:
            logger.warning(f"Failed to edit/send message: {e2}")
            return False
    except Exception as e:
        logger.warning(f"Failed to edit message: {e}")
        return False
