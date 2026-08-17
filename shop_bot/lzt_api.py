import aiohttp
import random
import logging
import time
from datetime import datetime, timezone

from config import LZT_TOKEN

BASE_URL = "https://prod-api.lzt.market"
logger = logging.getLogger(__name__)

import asyncio
from config import LZT_RATE_LIMIT

_lzt_semaphore = asyncio.Semaphore(3)
_lzt_lock = asyncio.Lock()

# Отдельный лимит для методов поиска категории:
# по документации LZT — 20 запросов/мин (3 секунды между запросами), иначе 429.
_search_lock = asyncio.Lock()
_last_search_ts = 0.0
SEARCH_MIN_INTERVAL = 3.0

# Происхождения аккаунтов, которые исключаем ВСЕГДА (фишинг и стиллер запрещены)
BLOCKED_ORIGINS = ("phishing", "stealer")


async def lzt_request(endpoint: str, method="GET", params=None, json_data=None):
    async with _lzt_semaphore:
        async with _lzt_lock:
            await asyncio.sleep(LZT_RATE_LIMIT)

    headers = {
        "Authorization": f"Bearer {LZT_TOKEN}",
        "Content-Type": "application/json",
    }
    url = f"{BASE_URL}{endpoint}"

    if isinstance(params, list):
        param_str = "&".join(f"{k}={v}" for k, v in params)
    else:
        param_str = "&".join(f"{k}={v}" for k, v in (params or {}).items())
    full_url = f"{url}?{param_str}" if param_str else url
    logger.info(f"LZT REQUEST: {method} {full_url}")

    last_exception = None
    for attempt in range(3):
        async with aiohttp.ClientSession() as session:
            try:
                # Для POST (fast-buy / check-account) LZT рекомендует большой таймаут
                timeout = aiohttp.ClientTimeout(total=15 if method == "GET" else 60)
                if method == "GET":
                    async with session.get(url, headers=headers, params=params, timeout=timeout) as resp:
                        text = await resp.text()
                        logger.info(f"LZT RESPONSE: status={resp.status}, body={text[:500]}")
                        try:
                            data = __import__("json").loads(text)
                        except Exception:
                            data = {"error": "Invalid JSON", "raw": text[:500]}
                        data["_http_status"] = resp.status
                        if resp.status == 401:
                            data["_token_expired"] = True
                        return data
                elif method == "POST":
                    async with session.post(url, headers=headers, json=json_data, params=params, timeout=timeout) as resp:
                        text = await resp.text()
                        logger.info(f"LZT POST RESPONSE: status={resp.status}, body={text[:500]}")
                        try:
                            data = __import__("json").loads(text)
                        except Exception:
                            data = {"error": "Invalid JSON", "raw": text[:500]}
                        data["_http_status"] = resp.status
                        if resp.status == 401:
                            data["_token_expired"] = True
                        return data
                elif method == "PUT":
                    async with session.put(url, headers=headers, json=json_data, timeout=timeout) as resp:
                        text = await resp.text()
                        try:
                            data = __import__("json").loads(text)
                        except Exception:
                            data = {"error": "Invalid JSON", "raw": text[:500]}
                        data["_http_status"] = resp.status
                        return data
            except Exception as e:
                logger.error(f"LZT API exception (attempt {attempt+1}/3): {e}")
                last_exception = e
                await asyncio.sleep(1 * (attempt + 1))

    return {"error": str(last_exception), "_http_status": 0}


def _extract_items(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ["items", "data", "result", "accounts", "lots"]:
            val = data.get(key)
            if isinstance(val, list):
                return val
            if isinstance(val, dict):
                for subkey in ["items", "data", "result", "accounts"]:
                    subval = val.get(subkey)
                    if isinstance(subval, list):
                        return subval
    return []


def _normalize_item(item):
    if not isinstance(item, dict):
        return None

    # Цена: с currency=rub поле price уже в рублях; rub_price — запасной вариант
    price_raw = item.get("price") or item.get("rub_price") or item.get("price_value") or item.get("cost") or item.get("amount") or 0
    try:
        price = float(price_raw)
    except (ValueError, TypeError):
        price = 0
    if price <= 0:
        return None

    item_id = item.get("item_id") or item.get("id") or item.get("itemId") or item.get("lot_id")

    # API возвращает плоские поля: item_origin / resale_item_origin / telegram_*.
    # Вложенного объекта "telegram" в ответе нет — он оставлен только как фолбэк.
    origin = item.get("item_origin") or item.get("origin") or ""
    resale_origin = item.get("resale_item_origin") or ""
    country = item.get("telegram_country") or item.get("country") or ""

    telegram_data = item.get("telegram", {})
    if not isinstance(telegram_data, dict):
        telegram_data = {}

    # Тип регистрации выводим из origin: autoreg = вирт. номер, self_registration = саморег (физ)
    registration_type = telegram_data.get("registration", "")
    if not registration_type:
        if origin == "autoreg":
            registration_type = "virtual"
        elif origin in ("self_registration", "personal"):
            registration_type = "manual"

    has_password = item.get("telegram_password", telegram_data.get("password", 0))
    spam_block = item.get("telegram_spam_block", telegram_data.get("spam_block", ""))

    # Дата регистрации / возраст: telegram_birthday — unix timestamp
    reg_date = None
    item_age_days = None
    birthday = item.get("telegram_birthday")
    if birthday:
        try:
            b = int(birthday)
            reg_date = datetime.fromtimestamp(b, tz=timezone.utc).strftime("%Y-%m-%d")
            item_age_days = max(0, (int(time.time()) - b) // 86400)
        except (ValueError, TypeError, OSError):
            reg_date = None
            item_age_days = None
    if item_age_days is None:
        item_age_days = telegram_data.get("account_age") or telegram_data.get("age") or telegram_data.get("days")
        if item_age_days is not None:
            try:
                item_age_days = int(item_age_days)
            except (ValueError, TypeError):
                item_age_days = None
    if reg_date is None:
        reg_date = telegram_data.get("registration_date") or telegram_data.get("reg_date") or telegram_data.get("created")

    has_avatar = bool(telegram_data.get("avatar", False))

    contacts_count = item.get("telegram_contacts_count", telegram_data.get("contacts") or telegram_data.get("contact_count"))
    if contacts_count is not None:
        try:
            contacts_count = int(contacts_count)
        except (ValueError, TypeError):
            contacts_count = None

    has_premium = bool(item.get("telegram_premium", telegram_data.get("premium", 0)))

    return {
        "item_id": item_id,
        "title": item.get("title", ""),
        "description": item.get("description", ""),
        "price": price,
        "country": country,
        "origin": (origin or "").lower(),
        "resale_origin": (resale_origin or "").lower(),
        "registration_type": registration_type,
        "spam_block": spam_block,
        "has_password": bool(has_password),
        "verified": bool(item.get("verified", False)),
        "item_age_days": item_age_days,
        "has_avatar": has_avatar,
        "reg_date": reg_date,
        "contacts_count": contacts_count,
        "has_premium": has_premium,
        "raw": item,
    }


async def get_lzt_balance():
    """
    GET /me — профиль и баланс.
    Возвращает dict пользователя с полем balance на верхнем уровне.

    FIX: LZT возвращает общий balance (например 3.00 ₽), но для покупки аккаунтов
    используется отдельный баланс в массиве balances с type="account".
    Берём именно его, иначе бот думает что денег нет.
    """
    data = await lzt_request("/me", method="GET")
    if isinstance(data, dict) and isinstance(data.get("user"), dict):
        merged = dict(data["user"])

        # Ищем баланс для покупки аккаунтов (type="account")
        balances = merged.get("balances", [])
        account_balance = None
        for b in balances:
            if isinstance(b, dict) and b.get("type") == "account":
                try:
                    account_balance = float(b.get("balance", 0))
                except (ValueError, TypeError):
                    account_balance = 0.0
                break

        if account_balance is not None:
            merged["balance"] = account_balance
        else:
            # fallback на старый общий баланс
            try:
                merged["balance"] = float(merged.get("balance", 0))
            except (ValueError, TypeError):
                merged["balance"] = 0.0

        for flag in ("_http_status", "_token_expired"):
            if flag in data:
                merged[flag] = data[flag]
        return merged
    return data


async def cancel_buy(item_id: int):
    endpoint = f"/{item_id}/cancel"
    return await lzt_request(endpoint, method="POST")


async def search_telegram_accounts(country: str = None, account_type: str = None):
    # Только документированные параметры API (lzt-market.readme.io/reference/categorytelegram)
    params = [
        ("page", "1"),
        ("nsb", "1"),                     # не продавались ранее (not sold before)
        ("order_by", "price_to_up"),
        ("spam", "no"),                   # без спам-блока
        ("password", "no"),               # без облачного пароля
        ("currency", "rub"),
    ]
    if country:
        params.append(("country[]", country))

    # Тип аккаунта задаётся через origin (параметра telegram[registration] в API нет):
    #   autoreg           — авторег (виртуальные номера)
    #   self_registration — саморег (физ. SIM)
    # origin[] одновременно исключает phishing/stealer/brute и т.д.
    if account_type == "autoreg":
        params.append(("origin[]", "autoreg"))
    elif account_type == "samoreg":
        params.append(("origin[]", "self_registration"))
    else:
        for blocked in BLOCKED_ORIGINS:
            params.append(("not_origin[]", blocked))

    # Лимит поиска: 20 запросов/мин — выдерживаем паузу 3 сек
    global _last_search_ts
    async with _search_lock:
        wait = SEARCH_MIN_INTERVAL - (time.monotonic() - _last_search_ts)
        if wait > 0:
            await asyncio.sleep(wait)
        data = await lzt_request("/telegram", method="GET", params=params)
        _last_search_ts = time.monotonic()

    if data.get("_token_expired"):
        return {"error": "token_expired", "items": []}

    http_status = data.get("_http_status", 200)
    if http_status != 200:
        logger.warning(f"LZT search failed: status={http_status}, body={str(data)[:300]}")
        return {"error": f"http_{http_status}", "items": []}

    items = _extract_items(data)
    total = data.get("totalItems")

    normalized = []
    for item in items:
        norm = _normalize_item(item)
        if norm:
            # Жёсткий клиентский фильтр: фишинг и стиллер исключены всегда,
            # включая перепродажу лотов с таким исходным происхождением
            if norm.get("has_password"):
                continue
            if norm.get("origin") in BLOCKED_ORIGINS:
                continue
            if norm.get("resale_origin") in BLOCKED_ORIGINS:
                continue
            normalized.append(norm)

    logger.info(f"LZT search returned {len(normalized)} valid items for country={country}, type={account_type}")
    return {"items": normalized, "total": total}


async def fast_buy(item_id: int, price: int = None):
    endpoint = f"/{item_id}/fast-buy"
    if price:
        return await lzt_request(endpoint, method="POST", json_data={"price": price})
    return await lzt_request(endpoint, method="POST")


async def confirm_buy(item_id: int, price: int = None):
    endpoint = f"/{item_id}/confirm-buy"
    if price:
        return await lzt_request(endpoint, method="POST", json_data={"price": price})
    return await lzt_request(endpoint, method="POST")


async def get_account_data_lzt(item_id: int):
    """
    POST /{item_id}/check-account — проверка аккаунта.
    Данные для выдачи (loginData) поднимаем на верхний уровень,
    чтобы handlers/cart.py читал login/password/session напрямую.
    """
    endpoint = f"/{item_id}/check-account"
    data = await lzt_request(endpoint, method="POST")
    if isinstance(data, dict) and isinstance(data.get("item"), dict):
        item = data["item"]
        login_data = item.get("loginData") or {}
        data["login"] = login_data.get("login") or item.get("login")
        data["password"] = login_data.get("password") or ""
        data["session"] = login_data.get("raw") or ""
    return data


async def reset_sessions_lzt(item_id: int):
    endpoint = f"/{item_id}/telegram-reset-authorizations"
    return await lzt_request(endpoint, method="POST")


async def validate_account_lzt(item_id: int):
    endpoint = f"/{item_id}/check-account"
    return await lzt_request(endpoint, method="POST")


def demo_search(country_code: str, account_type: str):
    country_names = {
        "US": "США", "KZ": "Казахстан", "IN": "Индия", "ID": "Индонезия",
        "PH": "Филиппины", "VN": "Вьетнам", "BR": "Бразилия", "AR": "Аргентина",
        "TR": "Турция", "RO": "Румыния", "PL": "Польша", "DE": "Германия",
        "GB": "Великобритания", "IT": "Италия", "ES": "Испания", "FR": "Франция",
        "NL": "Нидерланды", "CZ": "Чехия", "BG": "Болгария", "MX": "Мексика",
        "CL": "Чили", "PE": "Перу", "CO": "Колумбия", "TH": "Таиланд",
        "MY": "Малайзия", "PK": "Пакистан", "BD": "Бангладеш", "EG": "Египет",
        "MA": "Марокко", "NG": "Нигерия", "KE": "Кения", "ZA": "ЮАР",
    }
    name = country_names.get(country_code, country_code)
    base_price = random.randint(30, 120)
    age = random.randint(10, 365)
    return [{
        "item_id": random.randint(100000, 999999),
        "title": f"Telegram {account_type} {name}",
        "price": base_price,
        "country": country_code,
        "account_type": account_type,
        "origin": "autoreg" if account_type == "autoreg" else "self_registration",
        "resale_origin": "",
        "has_password": False,
        "item_age_days": age,
        "has_avatar": random.choice([True, False]),
        "reg_date": f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
        "contacts_count": random.randint(0, 50),
        "has_premium": random.choice([True, False]),
    }]


def demo_buy(item_id: int):
    return {
        "status": "ok",
        "item_id": item_id,
        "price": random.randint(30, 120),
        "message": "Purchase successful (demo)",
    }


def demo_get_data(item_id: int):
    return {
        "status": "ok",
        "item_id": item_id,
        "login": f"+{random.randint(1000000000, 9999999999)}",
        "password": "",
        "session": f"demo_session_{item_id}_{random.randint(1000,9999)}",
        "2fa": random.choice([True, False]),
    }
