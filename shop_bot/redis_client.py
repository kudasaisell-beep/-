import redis
import json
import logging
import time
from config import REDIS_URL

# Таймауты, чтобы при недоступном Redis бот не зависал
r = redis.from_url(
    REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)

# ========== Доступность Redis (backoff между попытками переподключения) ==========
# Если Redis упал, НЕ дёргаем его при каждом вызове (иначе спам в логах
# и лишние 2-секундные таймауты на каждую операцию), а работаем с
# in-memory fallback и пробуем переподключиться раз в REDIS_RETRY_AFTER секунд.
REDIS_RETRY_AFTER = 60  # секунд между попытками переподключения
_redis_down_until = 0.0


def _redis_available() -> bool:
    return time.time() >= _redis_down_until


def _mark_redis_down(e: Exception, context: str):
    """Помечает Redis как недоступный; логирует только при переходе в down."""
    global _redis_down_until
    was_down = _redis_down_until > time.time()
    _redis_down_until = time.time() + REDIS_RETRY_AFTER
    if not was_down:
        logging.warning(
            f"Redis unavailable ({context}), using in-memory fallback; "
            f"next reconnect attempt in {REDIS_RETRY_AFTER}s: {e}"
        )


# ========== In-memory fallback (когда Redis недоступен) ==========
_mem_locks = {}       # item_id -> (user_id, expires_at)
_mem_cooldowns = {}   # user_id -> expires_at
_mem_paused = {"value": False}
_mem_errors = []      # последние ошибки


def _cleanup_mem():
    """Удаляет протухшие in-memory ключи."""
    now = time.time()
    for d in (_mem_locks, _mem_cooldowns):
        expired = [k for k, v in d.items() if v[-1] <= now]
        for k in expired:
            d.pop(k, None)


def acquire_item_lock(item_id: int, user_id: int, ttl: int = 300) -> bool:
    """Блокировка лота на 5 минут. Возвращает True если удалось заблокировать."""
    key = f"lzt_lock:{item_id}"
    if _redis_available():
        try:
            # NX — только если ключа нет
            return r.set(key, str(user_id), nx=True, ex=ttl) is not None
        except redis.RedisError as e:
            _mark_redis_down(e, "acquire_item_lock")
    _cleanup_mem()
    if item_id in _mem_locks:
        return False
    _mem_locks[item_id] = (user_id, time.time() + ttl)
    return True


def release_item_lock(item_id: int):
    if _redis_available():
        try:
            r.delete(f"lzt_lock:{item_id}")
        except redis.RedisError as e:
            _mark_redis_down(e, "release_item_lock")
    _mem_locks.pop(item_id, None)


def set_user_cooldown(user_id: int, seconds: int):
    if _redis_available():
        try:
            r.setex(f"cooldown:{user_id}", seconds, "1")
            return
        except redis.RedisError as e:
            _mark_redis_down(e, "set_user_cooldown")
    _mem_cooldowns[user_id] = time.time() + seconds


def is_user_cooldown(user_id: int) -> bool:
    if _redis_available():
        try:
            return r.exists(f"cooldown:{user_id}") == 1
        except redis.RedisError as e:
            _mark_redis_down(e, "is_user_cooldown")
    _cleanup_mem()
    return user_id in _mem_cooldowns


def log_error_to_redis(error_text: str):
    if _redis_available():
        try:
            r.lpush("bot_errors", error_text)
            r.ltrim("bot_errors", 0, 99)
            return
        except redis.RedisError as e:
            _mark_redis_down(e, "log_error_to_redis")
    _mem_errors.insert(0, error_text)
    del _mem_errors[100:]


def get_recent_errors(limit: int = 10) -> list:
    if _redis_available():
        try:
            return r.lrange("bot_errors", 0, limit - 1)
        except redis.RedisError as e:
            _mark_redis_down(e, "get_recent_errors")
    return _mem_errors[:limit]


# ========== PURCHASES PAUSED (Redis-based, thread-safe) ==========

def set_purchases_paused(paused: bool):
    _mem_paused["value"] = paused
    if _redis_available():
        try:
            r.set("purchases_paused", "1" if paused else "0")
        except redis.RedisError as e:
            _mark_redis_down(e, "set_purchases_paused")


def is_purchases_paused() -> bool:
    if _redis_available():
        try:
            return r.get("purchases_paused") == "1"
        except redis.RedisError as e:
            _mark_redis_down(e, "is_purchases_paused")
    return _mem_paused["value"]
