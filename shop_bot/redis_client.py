import redis
import json
import logging
import time
import threading
from config import REDIS_URL

r = redis.from_url(
    REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)

REDIS_RETRY_AFTER = 60
_redis_down_until = 0.0

def _redis_available() -> bool:
    return time.time() >= _redis_down_until

def _mark_redis_down(e: Exception, context: str):
    global _redis_down_until
    was_down = _redis_down_until > time.time()
    _redis_down_until = time.time() + REDIS_RETRY_AFTER
    if not was_down:
        logging.warning(
            f"Redis unavailable ({context}), using in-memory fallback; "
            f"next reconnect attempt in {REDIS_RETRY_AFTER}s: {e}"
        )

_mem_locks = {}
_mem_cooldowns = {}
_mem_paused = {"value": False}
_mem_errors = []
# FIX 33: threading lock for in-memory fallback race condition
_mem_lock = threading.Lock()

def _cleanup_mem():
    now = time.time()
    for d in (_mem_locks, _mem_cooldowns):
        expired = [k for k, v in d.items() if v[-1] <= now]
        for k in expired:
            d.pop(k, None)

def acquire_item_lock(item_id: int, user_id: int, ttl: int = 300) -> bool:
    key = f"lzt_lock:{item_id}"
    if _redis_available():
        try:
            return r.set(key, str(user_id), nx=True, ex=ttl) is not None
        except redis.RedisError as e:
            _mark_redis_down(e, "acquire_item_lock")
    with _mem_lock:
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
    with _mem_lock:
        _mem_locks.pop(item_id, None)

def set_user_cooldown(user_id: int, seconds: int):
    if _redis_available():
        try:
            r.setex(f"cooldown:{user_id}", seconds, "1")
            return
        except redis.RedisError as e:
            _mark_redis_down(e, "set_user_cooldown")
    with _mem_lock:
        _mem_cooldowns[user_id] = time.time() + seconds

def is_user_cooldown(user_id: int) -> bool:
    if _redis_available():
        try:
            return r.exists(f"cooldown:{user_id}") == 1
        except redis.RedisError as e:
            _mark_redis_down(e, "is_user_cooldown")
    with _mem_lock:
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
    with _mem_lock:
        _mem_errors.insert(0, error_text)
        del _mem_errors[100:]

def get_recent_errors(limit: int = 10) -> list:
    if _redis_available():
        try:
            return r.lrange("bot_errors", 0, limit - 1)
        except redis.RedisError as e:
            _mark_redis_down(e, "get_recent_errors")
    with _mem_lock:
        return _mem_errors[:limit]

def set_purchases_paused(paused: bool):
    with _mem_lock:
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
    with _mem_lock:
        return _mem_paused["value"]

# FIX 32: Redis-based rate limiting for multi-instance support
def check_redis_rate_limit(user_id: int, action: str, max_count: int, window_seconds: int) -> dict:
    key = f"ratelimit:{action}:{user_id}"
    if _redis_available():
        try:
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            results = pipe.execute()
            count = results[0]
            if count > max_count:
                ttl = r.ttl(key)
                return {"ok": False, "retry_after": max(1, ttl)}
            return {"ok": True, "remaining": max_count - count}
        except redis.RedisError as e:
            _mark_redis_down(e, "check_redis_rate_limit")
    # Fallback to memory
    mem_key = f"{action}:{user_id}"
    with _mem_lock:
        now = time.time()
        if mem_key in _mem_cooldowns:
            if isinstance(_mem_cooldowns[mem_key], tuple):
                count, window_end = _mem_cooldowns[mem_key]
                if now > window_end:
                    _mem_cooldowns[mem_key] = (1, now + window_seconds)
                    return {"ok": True, "remaining": max_count - 1}
                if count >= max_count:
                    return {"ok": False, "retry_after": int(window_end - now)}
                _mem_cooldowns[mem_key] = (count + 1, window_end)
                return {"ok": True, "remaining": max_count - count - 1}
        _mem_cooldowns[mem_key] = (1, now + window_seconds)
        return {"ok": True, "remaining": max_count - 1}
