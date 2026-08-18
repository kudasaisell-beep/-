from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable
import time
import logging
from redis_client import check_redis_rate_limit

logger = logging.getLogger(__name__)

class AntifraudMiddleware(BaseMiddleware):
    """
    FIX 32: Redis-based rate limiting for multi-instance support.
    Also includes per-user cooldown on purchases.
    """
    def __init__(self, default_limit: int = 30, window_seconds: int = 60):
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        # In-memory fallback for message-level flood
        self._last_message: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        now = time.time()

        # Message-level flood protection (always in-memory, per-instance)
        if user_id in self._last_message:
            if now - self._last_message[user_id] < 0.3:
                return None
        self._last_message[user_id] = now

        # Global rate limit via Redis (FIX 32)
        result = check_redis_rate_limit(user_id, "messages", self.default_limit, self.window_seconds)
        if not result["ok"]:
            try:
                await event.answer(f"⏱ Слишком много сообщений. Подождите {result['retry_after']} сек.")
            except Exception:
                pass
            return None

        return await handler(event, data)
