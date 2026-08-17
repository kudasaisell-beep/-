import time
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

logger = logging.getLogger(__name__)

# In-memory rate limiter (для продакшена лучше Redis)
_user_timestamps: Dict[int, float] = {}
_user_counts: Dict[int, int] = {}

RATE_LIMIT_SECONDS = 1.0   # минимум 1 сек между запросами
MAX_REQUESTS_PER_MIN = 30  # макс 30 запросов в минуту


class AntifraudMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        user_id = user.id
        now = time.time()

        # Cooldown между любыми запросами
        last = _user_timestamps.get(user_id, 0)
        if now - last < RATE_LIMIT_SECONDS:
            logger.warning(f"Rate limit hit for user {user_id}")
            return None
        _user_timestamps[user_id] = now

        # Лимит запросов в минуту
        if now - last > 60:
            _user_counts[user_id] = 1
        else:
            _user_counts[user_id] = _user_counts.get(user_id, 0) + 1

        if _user_counts[user_id] > MAX_REQUESTS_PER_MIN:
            logger.warning(f"Too many requests from user {user_id}")
            return None

        return await handler(event, data)
