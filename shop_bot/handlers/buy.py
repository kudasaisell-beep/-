from aiogram import Router, types, F
from tg_utils import safe_answer, safe_edit, send_safe_message
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio
import json

from database import (
    get_account, add_purchase, update_account_status, get_user, add_account,
    add_favorite, get_favorites, remove_favorite,
    create_pending_purchase, finalize_pending_purchase,
    deduct_balance_only, refund_balance, add_log, add_to_cart,
    check_rate_limit
)
from lzt_api import (
    search_items, reserve_item, confirm_buy, get_item_secure_data,
    cancel_buy, verify_purchase, get_item_full_info
)
from keyboards import (
    buy_main_kb, countries_kb, country_type_kb,
    back_to_main_kb, back_to_buy_kb, back_to_countries_kb,
    lzt_cart_kb, progress_kb, favorites_kb, account_card_kb, insurance_kb,
    post_purchase_kb, subcategory_kb
)
from config import ADMIN_CHAT_ID, TOPIC_PURCHASES, USER_BUY_COOLDOWN
from redis_client import is_purchases_paused
from redis_client import acquire_item_lock, release_item_lock, set_user_cooldown, is_user_cooldown, check_redis_rate_limit
from tg_validator import validate_account

router = Router()

user_filters = {}
user_lzt_cart = {}
user_pending_item = {}

_purchase_locks: dict[int, asyncio.Lock] = {}

def _get_user_lock(user_id: int) -> asyncio.Lock:
    if user_id not in _purchase_locks:
        _purchase_locks[user_id] = asyncio.Lock()
    return _purchase_locks[user_id]

class SearchState(StatesGroup):
    waiting_country = State()

# ========== КАТЕГОРИИ И ПОДКАТЕГОРИИ ==========

SUBCAT_INFO = {
    # Мессенджеры
    "telegram": {"name": "Telegram", "emoji": "📱", "has_types": True},
    "tiktok": {"name": "TikTok", "emoji": "🎵", "has_types": False},
    "discord": {"name": "Discord", "emoji": "💬", "has_types": False},
    "instagram": {"name": "Instagram", "emoji": "📸", "has_types": False},
    "twitter": {"name": "Twitter/X", "emoji": "🐦", "has_types": False},
    "vk": {"name": "VK", "emoji": "🔵", "has_types": False},
    "reddit": {"name": "Reddit", "emoji": "🔴", "has_types": False},
    # Игры
    "genshin": {"name": "Genshin Impact", "emoji": "🗡️", "has_types": False},
    "minecraft": {"name": "Minecraft", "emoji": "⛏️", "has_types": False},
    "steam": {"name": "Steam", "emoji": "🎮", "has_types": False},
    "fortnite": {"name": "Fortnite", "emoji": "🔫", "has_types": False},
    "valorant": {"name": "Valorant", "emoji": "🎯", "has_types": False},
    "roblox": {"name": "Roblox", "emoji": "🧱", "has_types": False},
    "epic": {"name": "Epic Games", "emoji": "🎲", "has_types": False},
    # Сервисы
    "spotify": {"name": "Spotify", "emoji": "🎧", "has_types": False},
    "netflix": {"name": "Netflix", "emoji": "🎬", "has_types": False},
    "chatgpt": {"name": "ChatGPT", "emoji": "🤖", "has_types": False},
    "canva": {"name": "Canva", "emoji": "🎨", "has_types": False},
    "youtube": {"name": "YouTube Premium", "emoji": "📺", "has_types": False},
    "icloud": {"name": "iCloud", "emoji": "☁️", "has_types": False},
}

country_map = {
    "US": ("США", "🇺🇸"), "KZ": ("Казахстан", "🇰🇿"), "IN": ("Индия", "🇮🇳"),
    "ID": ("Индонезия", "🇮🇩"), "PH": ("Филиппины", "🇵🇭"), "VN": ("Вьетнам", "🇻🇳"),
    "BR": ("Бразилия", "🇧🇷"), "AR": ("Аргентина", "🇦🇷"), "TR": ("Турция", "🇹🇷"),
    "RO": ("Румыния", "🇷🇴"), "PL": ("Польша", "🇵🇱"), "DE": ("Германия", "🇩🇪"),
    "GB": ("Великобритания", "🇬🇧"), "IT": ("Италия", "🇮🇹"), "ES": ("Испания", "🇪🇸"),
    "FR": ("Франция", "🇫🇷"), "NL": ("Нидерланды", "🇳🇱"), "CZ": ("Чехия", "🇨🇿"),
    "BG": ("Болгария", "🇧🇬"), "MX": ("Мексика", "🇲🇽"), "CL": ("Чили", "🇨🇱"),
    "PE": ("Перу", "🇵🇪"), "CO": ("Колумбия", "🇨🇴"), "TH": ("Таиланд", "🇹🇭"),
    "MY": ("Малайзия", "🇲🇾"), "PK": ("Пакистан", "🇵🇰"), "BD": ("Бангладеш", "🇧🇩"),
    "EG": ("Египет", "🇪🇬"), "MA": ("Марокко", "🇲🇦"), "NG": ("Нигерия", "🇳🇬"),
    "KE": ("Кения", "🇰🇪"), "ZA": ("ЮАР", "🇿🇦"), "RU": ("Россия", "🇷🇺"),
    "UA": ("Украина", "🇺🇦"), "BY": ("Беларусь", "🇧🇾"),
}

def get_country_name(code):
    return country_map.get(code, (code, ""))[0]

def get_country_flag(code):
    return country_map.get(code, ("", "🏳️"))[1]

def discount_percent(qty: int) -> float:
    if qty >= 4:
        return 0.07
    if qty == 3:
        return 0.05
    if qty == 2:
        return 0.03
    return 0.0

def calculate_price(qty: int, base_price: float) -> float:
    disc = discount_percent(qty)
    total = qty * base_price * (1 - disc)
    return round(total, 2)

# ========== ПОЛНАЯ ИНФОРМАЦИЯ ИЗ LZT ==========

def build_full_item_card(item: dict, base_price: float, country_code: str, account_type: str, subcat_key: str = "telegram") -> str:
    """Строит карточку товара с ПОЛНОЙ информацией из LZT."""
    name = get_country_name(country_code)
    flag = get_country_flag(country_code)
    subcat = SUBCAT_INFO.get(subcat_key, {"name": subcat_key, "emoji": "📦"})

    # Базовая информация
    type_label = "🧑 Саморег (физ)" if account_type == "samoreg" else "🤖 Авторег (вирт)" if account_type == "autoreg" else "📦 Аккаунт"
    age = item.get("item_age_days")
    age_str = f"{age} дней" if age is not None else "неизвестно"
    avatar = "✅ Есть" if item.get("has_avatar") else "❌ Нет"
    reg = item.get("reg_date") or "неизвестно"
    contacts = item.get("contacts_count")
    contacts_str = f"{contacts}" if contacts is not None else "неизвестно"
    premium = "✅ Есть" if item.get("has_premium") else "❌ Нет"

    # Информация о продавце
    seller = item.get("seller", {})
    seller_name = item.get("seller_username", "неизвестно")
    seller_rating = item.get("seller_rating", 0)

    # Поля из raw LZT
    raw = item.get("raw", {})

    text = (
        f"{subcat['emoji']} <b>{subcat['name']}</b>\n"
        f"{flag} <b>{name}</b> — {type_label}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 <b>Цена:</b> {int(base_price)}₽\n"
        f"🆔 <b>Item ID:</b> <code>{item.get('item_id', '?')}</code>\n\n"
        f"📊 <b>Характеристики:</b>\n"
        f"  ⏱ Возраст: {age_str}\n"
        f"  🖼 Аватарка: {avatar}\n"
        f"  📅 Регистрация: {reg}\n"
        f"  👥 Контакты: {contacts_str}\n"
        f"  ⭐ Премиум: {premium}\n"
        f"  ✅ Верифицирован: {'Да' if item.get('verified') else 'Нет'}\n"
        f"  🔒 Пароль: {'Есть' if item.get('has_password') else 'Нет'}\n"
        f"  🛡 Спамблок: {item.get('spam_block') or 'Нет'}\n\n"
    )

    # Дополнительная информация из raw
    if raw and isinstance(raw, dict):
        # Популяция, подписчики и т.д.
        followers = raw.get("followers") or raw.get("followers_count")
        if followers:
            text += f"  👥 Подписчики: {followers}\n"
        likes = raw.get("likes") or raw.get("likes_count")
        if likes:
            text += f"  ❤️ Лайки: {likes}\n"
        games = raw.get("games_count")
        if games:
            text += f"  🎮 Игр: {games}\n"
        level = raw.get("level")
        if level:
            text += f"  📊 Уровень: {level}\n"
        ar = raw.get("adventure_rank")
        if ar:
            text += f"  ⚔️ AR: {ar}\n"

    text += (
        f"\n🏪 <b>Продавец:</b> {seller_name}\n"
        f"  ⭐ Рейтинг: {seller_rating}\n\n"
        f"🛡 <b>Гарантия:</b> 24 часа (или пожизненная со страховкой)\n"
        f"🚫 <b>Источник:</b> Легальный (не брут/фишинг/стиллер)"
    )
    return text


def build_cart_text(user_id: int) -> str:
    cart = user_lzt_cart.get(user_id)
    if not cart:
        return "❌ Корзина пуста"
    name = cart["country_name"]
    account_type = cart["account_type"]
    qty = cart["qty"]
    base_price = cart["base_price"]
    available = len(cart["items"])
    disc = discount_percent(qty)
    total = calculate_price(qty, base_price)
    price_per = round(base_price * (1 - disc), 2)
    type_label = "саморег" if account_type == "samoreg" else "авторег" if account_type == "autoreg" else "аккаунт"
    text = (
        f"{name}\n"
        f"Тип: {type_label}\n"
        f"💰 Ваша цена: {int(base_price)}₽/шт\n"
        f"Количество: {qty} шт\n"
    )
    if disc > 0:
        text += f"Скидка: {int(disc * 100)}% ({int(price_per)}₽/шт)\n"
    text += f"\n📦 Доступно: <b>{available} шт</b>\nПокупаем {qty} шт?"
    return text


async def notify_admin_purchase(bot, text: str):
    if ADMIN_CHAT_ID:
        try:
            kwargs = {}
            if TOPIC_PURCHASES:
                kwargs["message_thread_id"] = TOPIC_PURCHASES
            await send_safe_message(bot, text, **kwargs)
        except Exception:
            pass


# ========== ГЛАВНОЕ МЕНЮ ПОКУПКИ ==========

@router.callback_query(F.data == "buy_menu")
async def buy_menu(callback: CallbackQuery):
    text = (
        "🛒 <b>Покупка</b>\n"
        "Выберите категорию товаров:\n\n"
        "💬 <b>Мессенджеры</b> — Telegram, TikTok, Discord, Instagram\n"
        "🎮 <b>Игры</b> — Genshin, Minecraft, Steam, Fortnite\n"
        "🎬 <b>Сервисы</b> — Spotify, Netflix, ChatGPT, Canva"
    )
    await safe_edit(callback, text, reply_markup=buy_main_kb)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("buy_category:"))
async def buy_category(callback: CallbackQuery):
    category = callback.data.split(":")[1]
    mapping = {
        "messengers": ("💬 Мессенджеры", "Выберите мессенджер или соцсеть:"),
        "games": ("🎮 Игры", "Выберите игру:"),
        "services": ("🎬 Сервисы", "Выберите сервис:"),
    }
    title, desc = mapping.get(category, ("Категория", "Выберите:"))
    text = f"{title}\n\n{desc}"
    await safe_edit(callback, text, reply_markup=subcategory_kb(category))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("buy_subcat:"))
async def buy_subcat(callback: CallbackQuery):
    subcat_key = callback.data.split(":")[1]
    info = SUBCAT_INFO.get(subcat_key, {"name": subcat_key, "emoji": "📦"})

    # Для Telegram — показываем страны (как раньше)
    # Для остальных — тоже страны, но без выбора типа
    text = (
        f"{info['emoji']} <b>{info['name']}</b>\n"
        f"Выберите страну аккаунта:"
    )
    await safe_edit(callback, text, reply_markup=countries_kb(page=0, subcat_key=subcat_key))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("country_page:"))
async def country_page(callback: CallbackQuery):
    parts = callback.data.split(":")
    page = int(parts[1])
    subcat_key = parts[2] if len(parts) > 2 else "telegram"
    text = "🌍 <b>Доступные страны</b>\nВыберите страну:"
    await safe_edit(callback, text, reply_markup=countries_kb(page=page, subcat_key=subcat_key))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("select_country:"))
async def select_country(callback: CallbackQuery):
    parts = callback.data.split(":")
    country_code = parts[1]
    subcat_key = parts[2] if len(parts) > 2 else "telegram"
    name = get_country_name(country_code)
    flag = get_country_flag(country_code)
    info = SUBCAT_INFO.get(subcat_key, {"name": subcat_key, "emoji": "📦"})

    if subcat_key == "telegram":
        text = (
            f"{flag} <b>{name}</b>\n"
            f"Выберите тип аккаунта:\n"
            f"• 🧑 <b>Саморег (физ)</b> — физические SIM\n"
            f"• 🤖 <b>Авторег (вирт)</b> — виртуальные номера"
        )
        await safe_edit(callback, text, reply_markup=country_type_kb(country_code, subcat_key))
    else:
        text = (
            f"{info['emoji']} <b>{info['name']}</b>\n"
            f"{flag} <b>{name}</b>\n"
            f"Нажмите, чтобы найти товары:"
        )
        await safe_edit(callback, text, reply_markup=country_type_kb(country_code, subcat_key))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("select_type:"))
async def select_type(callback: CallbackQuery):
    await safe_answer(callback)
    parts = callback.data.split(":")
    country_code = parts[1]
    account_type = parts[2]
    subcat_key = parts[3] if len(parts) > 3 else "telegram"

    name = get_country_name(country_code)
    flag = get_country_flag(country_code)
    type_label = "саморег" if account_type == "samoreg" else "авторег"

    await safe_edit(callback,
        f"⏳ <b>Загрузка карточек...</b>\n{progress_kb(0).inline_keyboard[0][0].text}",
        reply_markup=progress_kb(0)
    )

    lzt_result = await search_items(category=subcat_key, country=country_code, account_type=account_type)
    if isinstance(lzt_result, dict) and lzt_result.get("error") == "token_expired":
        text = f"{flag} <b>{name}</b>\n⚠️ <b>Каталог временно недоступен</b>"
        await safe_edit(callback, text, reply_markup=back_to_countries_kb)
        return

    lzt_items = lzt_result if isinstance(lzt_result, list) else lzt_result.get("items", [])

    if not lzt_items:
        text = f"{flag} <b>{name}</b>\n❌ Сейчас нет аккаунтов типа <b>{type_label}</b>."
        await safe_edit(callback, text, reply_markup=back_to_countries_kb)
        return

    lzt_prices = [item["price"] for item in lzt_items]
    avg_lzt = sum(lzt_prices) / len(lzt_prices)
    base_price = round(avg_lzt * 2, 2)
    top_items = lzt_items[:3]

    rec_text = "\n🎯 <b>Рекомендуем:</b>\n"
    for idx, item in enumerate(top_items, 1):
        age = item.get("item_age_days")
        age_str = f"{age}д" if age else "?"
        premium = "⭐" if item.get("has_premium") else ""
        rec_text += f"  {idx}. Аккаунт #{idx} — возраст {age_str} {premium}\n"

    first_item = lzt_items[0]
    card_text = build_full_item_card(first_item, base_price, country_code, account_type, subcat_key)
    full_text = card_text + rec_text + "\n👇 Выберите аккаунт или добавьте в корзину:"

    user_lzt_cart[callback.from_user.id] = {
        "country_code": country_code,
        "account_type": account_type,
        "subcat_key": subcat_key,
        "country_name": flag + " " + name,
        "items": lzt_items,
        "qty": 1,
        "base_price": base_price,
        "exact_match": True,
    }
    kb = account_card_kb(first_item["item_id"], base_price, country_code, account_type, subcat_key)
    await safe_edit(callback, full_text, reply_markup=kb)


@router.callback_query(F.data.startswith("cart_plus:"))
async def cart_plus(callback: CallbackQuery):
    parts = callback.data.split(":")
    country_code = parts[1]
    account_type = parts[2]
    subcat_key = parts[3] if len(parts) > 3 else "telegram"
    cart = user_lzt_cart.get(callback.from_user.id)
    if not cart:
        await safe_answer(callback, "❌ Сессия истекла", show_alert=True)
        return
    if cart["qty"] < len(cart["items"]):
        cart["qty"] += 1
        text = build_cart_text(callback.from_user.id)
        kb = lzt_cart_kb(country_code, account_type, cart["qty"], len(cart["items"]),
                         calculate_price(cart["qty"], cart["base_price"]), subcat_key)
        await safe_edit(callback, text, reply_markup=kb)
        await safe_answer(callback)


@router.callback_query(F.data.startswith("cart_minus:"))
async def cart_minus(callback: CallbackQuery):
    parts = callback.data.split(":")
    country_code = parts[1]
    account_type = parts[2]
    subcat_key = parts[3] if len(parts) > 3 else "telegram"
    cart = user_lzt_cart.get(callback.from_user.id)
    if not cart:
        await safe_answer(callback, "❌ Сессия истекла", show_alert=True)
        return
    if cart["qty"] > 1:
        cart["qty"] -= 1
        text = build_cart_text(callback.from_user.id)
        kb = lzt_cart_kb(country_code, account_type, cart["qty"], len(cart["items"]),
                         calculate_price(cart["qty"], cart["base_price"]), subcat_key)
        await safe_edit(callback, text, reply_markup=kb)
        await safe_answer(callback)


@router.callback_query(F.data.startswith("cart_remove:"))
async def cart_remove(callback: CallbackQuery):
    user_lzt_cart.pop(callback.from_user.id, None)
    await safe_edit(callback, "❌ Аккаунт убран из корзины.", reply_markup=back_to_countries_kb)
    await safe_answer(callback, "✅ Убрано")


@router.callback_query(F.data.startswith("add_to_cart:"))
async def add_to_cart_handler(callback: CallbackQuery):
    parts = callback.data.split(":")
    item_id_str = parts[1]
    subcat_key = parts[2] if len(parts) > 2 else "telegram"
    try:
        item_id = int(item_id_str)
    except (ValueError, TypeError):
        await safe_answer(callback, "❌ Некорректный ID товара", show_alert=True)
        return
    user_id = callback.from_user.id
    cart = user_lzt_cart.get(user_id)
    if not cart:
        await safe_answer(callback, "❌ Сессия истекла. Выберите страну заново.", show_alert=True)
        return
    item = None
    for it in cart["items"]:
        if it["item_id"] == item_id:
            item = it
            break
    if not item:
        await safe_answer(callback, "❌ Аккаунт не найден.", show_alert=True)
        return
    add_to_cart(
        user_id=user_id,
        item_id=item_id,
        country_code=cart["country_code"],
        country_name=cart["country_name"],
        account_type=cart["account_type"],
        price=cart["base_price"],
        cost_price=item["price"],
        item_age_days=item.get("item_age_days"),
        has_avatar=item.get("has_avatar", False),
        reg_date=item.get("reg_date"),
        contacts_count=item.get("contacts_count"),
        has_premium=item.get("has_premium", False),
    )
    add_log(user_id, "add_to_cart", f"item_id={item_id}, price={cart['base_price']}, subcat={subcat_key}")
    await safe_answer(callback, f"✅ Добавлено в корзину!\n{cart['country_name']} — {int(cart['base_price'])}₽", show_alert=True)


@router.callback_query(F.data.startswith("pre_buy:"))
async def pre_buy_handler(callback: CallbackQuery):
    parts = callback.data.split(":")
    item_id_str = parts[1]
    subcat_key = parts[2] if len(parts) > 2 else "telegram"
    try:
        item_id = int(item_id_str)
    except (ValueError, TypeError):
        await safe_answer(callback, "❌ Некорректный ID", show_alert=True)
        return
    user_id = callback.from_user.id
    cart = user_lzt_cart.get(user_id)
    if not cart:
        await safe_answer(callback, "❌ Сессия истекла", show_alert=True)
        return
    item = None
    for it in cart["items"]:
        if it["item_id"] == item_id:
            item = it
            break
    if not item:
        await safe_answer(callback, "❌ Аккаунт не найден", show_alert=True)
        return
    user_pending_item[user_id] = {
        "item": item,
        "cart": cart,
        "base_price": cart["base_price"],
        "subcat_key": subcat_key,
    }
    base = cart["base_price"]
    insured = round(base * 1.2, 2)
    text = (
        f"🛡 <b>Выберите тип гарантии</b>\n\n"
        f"📦 Аккаунт: <b>{cart['country_name']}</b>\n"
        f"💰 Базовая цена: <b>{int(base)}₽</b>\n\n"
        f"1️⃣ <b>Стандарт</b> — {int(base)}₽\n"
        f"   ✅ Гарантия 24 часа\n\n"
        f"2️⃣ <b>Страховка (+20%)</b> — {int(insured)}₽\n"
        f"   🛡 <b>Пожизненная гарантия</b>\n"
        f"   ✅ Возврат или замена навсегда"
    )
    await safe_edit(callback, text, reply_markup=insurance_kb)
    await safe_answer(callback)


@router.callback_query(F.data == "buy_insured")
async def buy_insured(callback: CallbackQuery):
    await _do_buy(callback, insured=True)


@router.callback_query(F.data == "buy_no_insurance")
async def buy_no_insurance(callback: CallbackQuery):
    await _do_buy(callback, insured=False)


async def _do_buy(callback: CallbackQuery, insured: bool):
    user_id = callback.from_user.id
    async with _get_user_lock(user_id):
        pending = user_pending_item.pop(user_id, None)
        if not pending:
            await safe_answer(callback, "❌ Сессия истекла", show_alert=True)
            return

        item = pending["item"]
        cart = pending["cart"]
        base_price = pending["base_price"]
        subcat_key = pending.get("subcat_key", "telegram")
        price = round(base_price * 1.2, 2) if insured else base_price

        if is_purchases_paused():
            await safe_answer(callback, "🛑 Покупки приостановлены.", show_alert=True)
            return

        user = get_user(user_id)
        if not user or user["balance"] < price:
            bal = user["balance"] if user else 0
            await safe_answer(callback, f"❌ Недостаточно средств. Баланс: {int(bal)}₽", show_alert=True)
            return

        if is_user_cooldown(user_id):
            await safe_answer(callback, f"⏱ Подождите {USER_BUY_COOLDOWN} сек", show_alert=True)
            return

        rl = check_redis_rate_limit(user_id, "buy", max_count=5, window_seconds=60)
        if not rl["ok"]:
            await safe_answer(callback, f"⏱ Слишком много покупок. Подождите {rl['retry_after']} сек.", show_alert=True)
            return

        item_id = item["item_id"]
        lzt_price = item["price"]

        if item_id is None:
            await safe_answer(callback, "❌ Некорректный товар", show_alert=True)
            return

        if not acquire_item_lock(item_id, user_id):
            await safe_answer(callback, "⚠️ Этот аккаунт уже покупают", show_alert=True)
            return

        # Списываем баланс заранее
        deduct = deduct_balance_only(user_id, price)
        if not deduct["ok"]:
            release_item_lock(item_id)
            await safe_answer(callback, f"❌ {deduct.get('error')}", show_alert=True)
            return

        await safe_answer(callback, "⏳ Резервируем аккаунт...")
        await safe_edit(callback, "⏳ <b>Резервирование...</b>\n" + progress_kb(1).inline_keyboard[0][0].text, reply_markup=progress_kb(1))

        # Резервируем на LZT
        reserve = await reserve_item(item_id)
        if reserve.get("error") or not reserve.get("status"):
            refund_balance(user_id, price)
            release_item_lock(item_id)
            await safe_edit(callback, "❌ Резервирование не удалось. Попробуйте позже.", reply_markup=back_to_main_kb)
            return

        # Получаем данные
        await safe_edit(callback, "⏳ <b>Получение данных...</b>\n" + progress_kb(2).inline_keyboard[0][0].text, reply_markup=progress_kb(2))
        data_result = await get_item_secure_data(item_id)
        login = data_result.get("login", "")
        password = data_result.get("password", "")
        session = data_result.get("session", "")
        has_2fa = data_result.get("2fa", False)

        if data_result.get("error") or not login or not session:
            await cancel_buy(item_id)
            refund_balance(user_id, price)
            release_item_lock(item_id)
            await safe_edit(callback, "❌ Аккаунт недоступен. Баланс возвращён.", reply_markup=back_to_main_kb)
            return

        # Валидация сессии (только для Telegram)
        if subcat_key == "telegram":
            validation = await validate_account(session, login)
            if not validation["ok"]:
                await cancel_buy(item_id)
                refund_balance(user_id, price)
                release_item_lock(item_id)
                await safe_edit(callback, f"❌ Аккаунт не прошёл проверку: {validation.get('error')}\nБаланс возвращён.", reply_markup=back_to_main_kb)
                return

        # Подтверждаем покупку на LZT
        confirm = await confirm_buy(item_id)
        if confirm.get("error"):
            await cancel_buy(item_id)
            refund_balance(user_id, price)
            release_item_lock(item_id)
            await safe_edit(callback, "❌ Ошибка подтверждения. Баланс возвращён.", reply_markup=back_to_main_kb)
            return

        verify = await verify_purchase(item_id)
        if not verify["ok"]:
            await cancel_buy(item_id)
            refund_balance(user_id, price)
            release_item_lock(item_id)
            await safe_edit(callback, f"❌ Покупка не подтверждена на LZT ({verify.get('status')}). Баланс возвращён.", reply_markup=back_to_main_kb)
            return

        # Полная информация из LZT для сохранения
        full_lzt_info = item.get("raw", {})
        full_info_text = json.dumps(full_lzt_info, ensure_ascii=False, indent=2) if isinstance(full_lzt_info, dict) else str(full_lzt_info)

        account_data = f"Телефон: {login}\nПароль: {password}\nСессия: {session}"
        if has_2fa:
            account_data += "\n⚠️ На аккаунте включен 2FA"

        # Добавляем полную информацию из LZT
        account_data += f"\n\n📋 <b>Полная информация из LZT:</b>\n<pre>{full_info_text[:1500]}</pre>"

        pending_id = create_pending_purchase(user_id, item_id, price, lzt_price, account_data,
                                             cart["country_code"], cart["country_name"], cart["account_type"])

        result = finalize_pending_purchase(
            pending_id, user_id, price, lzt_price, account_data,
            cart["country_code"], cart["country_name"], cart["account_type"],
            item_age_days=item.get("item_age_days"),
            has_avatar=item.get("has_avatar", False),
            reg_date=item.get("reg_date"),
            contacts_count=item.get("contacts_count"),
            has_premium=item.get("has_premium", False)
        )

        if not result["ok"]:
            release_item_lock(item_id)
            await safe_edit(callback,
                f"⚠️ Аккаунт выдан, но произошла ошибка записи. Обратитесь в поддержку.\nItem ID: {item_id}",
                reply_markup=back_to_main_kb)
            if ADMIN_CHAT_ID:
                await send_safe_message(callback.bot,
                    f"🚨 Ошибка финализации покупки!\nItem ID: {item_id}\nUser: {user_id}\nError: {result.get('error')}",
                    chat_id=ADMIN_CHAT_ID)
            return

        release_item_lock(item_id)
        guarantee_text = "🛡 Пожизненная гарантия" if insured else "🛡 Гарантия 24 часа"
        type_label = "саморег" if cart["account_type"] == "samoreg" else "авторег"
        subcat_name = SUBCAT_INFO.get(subcat_key, {}).get("name", subcat_key)

        admin_text = (
            f"🛒 <b>Новая покупка!</b>\n"
            f"👤 Пользователь: <code>{user_id}</code>\n"
            f"📂 Категория: {subcat_name}\n"
            f"🌍 Страна: {cart['country_name']}\n"
            f"📱 Тип: {type_label}\n"
            f"💰 Сумма: {int(price)}₽\n"
            f"{guarantee_text}\n"
            f"💸 Себестоимость LZT: {int(lzt_price)}₽\n"
            f"📈 Прибыль: {int(price - lzt_price)}₽"
        )
        await notify_admin_purchase(callback.bot, admin_text)

        result_text = (
            f"✅ <b>Покупка успешна!</b>\n\n"
            f"📂 Категория: {subcat_name}\n"
            f"Страна: {cart['country_name']}\n"
            f"Тип: {type_label}\n"
            f"Цена: {int(price)}₽\n"
            f"{guarantee_text}\n\n"
            f"📦 Данные аккаунта:\n"
            f" <code>{account_data}</code>\n\n"
            f"💾 Сохраните их — они больше не будут показаны."
        )
        await safe_edit(callback, result_text, reply_markup=post_purchase_kb)
        set_user_cooldown(user_id, USER_BUY_COOLDOWN)


# ========== ОПТОВАЯ ПОКУПКА ==========

@router.callback_query(F.data.startswith("buy_lzt:"))
async def buy_lzt(callback: CallbackQuery):
    if is_purchases_paused():
        await safe_answer(callback, "🛑 Покупки приостановлены.", show_alert=True)
        return
    parts = callback.data.split(":")
    country_code = parts[1]
    account_type = parts[2]
    qty = int(parts[3])
    subcat_key = parts[4] if len(parts) > 4 else "telegram"
    user_id = callback.from_user.id

    async with _get_user_lock(user_id):
        cart = user_lzt_cart.get(user_id)
        if not cart:
            await safe_answer(callback, "❌ Сессия истекла.", show_alert=True)
            return

        available_count = len(cart["items"])
        if qty > available_count:
            await safe_answer(callback, f"❌ Доступно только {available_count} аккаунтов", show_alert=True)
            return

        total_price = calculate_price(qty, cart["base_price"])
        user = get_user(user_id)
        if not user or user["balance"] < total_price:
            bal = user["balance"] if user else 0
            await safe_answer(callback, f"❌ Недостаточно средств. Баланс: {int(bal)}₽", show_alert=True)
            return
        if is_user_cooldown(user_id):
            await safe_answer(callback, f"⏱ Подождите {USER_BUY_COOLDOWN} сек", show_alert=True)
            return

        rl = check_redis_rate_limit(user_id, "buy", max_count=5, window_seconds=60)
        if not rl["ok"]:
            await safe_answer(callback, f"⏱ Слишком много покупок. Подождите {rl['retry_after']} сек.", show_alert=True)
            return

        price_per = round(cart["base_price"] * (1 - discount_percent(qty)), 2)
        await safe_answer(callback, f"⏳ Покупаем {qty} аккаунт(ов)...")
        await safe_edit(callback, "⏳ <b>Покупка аккаунтов...</b>\n" + progress_kb(1).inline_keyboard[0][0].text, reply_markup=progress_kb(1))

        deduct = deduct_balance_only(user_id, total_price)
        if not deduct["ok"]:
            await safe_answer(callback, f"❌ {deduct.get('error')}", show_alert=True)
            return

        purchased_accounts = []
        total_lzt_cost = 0.0
        failed = 0
        used_item_ids = set()

        for i in range(qty):
            item = None
            for candidate in cart["items"]:
                if candidate["item_id"] not in used_item_ids:
                    item = candidate
                    break
            if not item:
                failed += 1
                continue
            item_id = item["item_id"]
            lzt_price = item["price"]

            if item_id is None:
                failed += 1
                continue

            used_item_ids.add(item_id)

            if not acquire_item_lock(item_id, user_id):
                failed += 1
                continue

            reserve = await reserve_item(item_id)
            if reserve.get("error") or not reserve.get("status"):
                release_item_lock(item_id)
                failed += 1
                continue

            data_result = await get_item_secure_data(item_id)
            login = data_result.get("login", "")
            password = data_result.get("password", "")
            session = data_result.get("session", "")
            has_2fa = data_result.get("2fa", False)

            if data_result.get("error") or not login or not session:
                await cancel_buy(item_id)
                release_item_lock(item_id)
                failed += 1
                if ADMIN_CHAT_ID:
                    await send_safe_message(callback.bot,
                        f"🚨 КРИТИЧЕСКАЯ ОШИБКА (опт): данные не получены!\nItem ID: {item_id}\nUser: {user_id}",
                        chat_id=ADMIN_CHAT_ID)
                continue

            if subcat_key == "telegram":
                validation = await validate_account(session, login)
                if not validation["ok"]:
                    await cancel_buy(item_id)
                    release_item_lock(item_id)
                    failed += 1
                    continue

            confirm = await confirm_buy(item_id)
            if confirm.get("error"):
                await cancel_buy(item_id)
                release_item_lock(item_id)
                failed += 1
                continue

            verify = await verify_purchase(item_id)
            if not verify["ok"]:
                await cancel_buy(item_id)
                release_item_lock(item_id)
                failed += 1
                continue

            full_lzt_info = item.get("raw", {})
            full_info_text = json.dumps(full_lzt_info, ensure_ascii=False, indent=2) if isinstance(full_lzt_info, dict) else str(full_lzt_info)

            account_data = f"Телефон: {login}\nПароль: {password}\nСессия: {session}"
            if has_2fa:
                account_data += "\n⚠️ На аккаунте включен 2FA"
            account_data += f"\n\n📋 Полная информация из LZT:\n<pre>{full_info_text[:1500]}</pre>"

            pending_id = create_pending_purchase(user_id, item_id, price_per, lzt_price, account_data,
                                                 cart["country_code"], cart["country_name"], cart["account_type"])
            tx = finalize_pending_purchase(
                pending_id, user_id, price_per, lzt_price, account_data,
                cart["country_code"], cart["country_name"], cart["account_type"],
                item_age_days=item.get("item_age_days"),
                has_avatar=item.get("has_avatar", False),
                reg_date=item.get("reg_date"),
                contacts_count=item.get("contacts_count"),
                has_premium=item.get("has_premium", False)
            )
            if not tx["ok"]:
                release_item_lock(item_id)
                failed += 1
                if ADMIN_CHAT_ID:
                    await send_safe_message(callback.bot,
                        f"🚨 Ошибка БД (опт): {tx.get('error')}\nItem ID: {item_id}\nUser: {user_id}",
                        chat_id=ADMIN_CHAT_ID)
                continue

            purchased_accounts.append(account_data)
            total_lzt_cost += lzt_price
            release_item_lock(item_id)

        if not purchased_accounts:
            refund_balance(user_id, total_price)
            await safe_edit(callback,
                "❌ <b>Покупка не удалась</b>\nНе удалось выкупить аккаунты.",
                reply_markup=back_to_main_kb)
            return

        actual_total = round(price_per * len(purchased_accounts), 2)
        if actual_total < total_price:
            refund_balance(user_id, total_price - actual_total)

        set_user_cooldown(user_id, USER_BUY_COOLDOWN)
        add_log(user_id, "buy_lzt_bulk", f"qty={len(purchased_accounts)}, total={actual_total}, subcat={subcat_key}")
        type_label = "саморег" if cart["account_type"] == "samoreg" else "авторег"
        subcat_name = SUBCAT_INFO.get(subcat_key, {}).get("name", subcat_key)
        admin_text = (
            f"🛒 <b>Новая покупка!</b>\n"
            f"👤 Пользователь: <code>{user_id}</code>\n"
            f"📂 Категория: {subcat_name}\n"
            f"🌍 Страна: {cart['country_name']}\n"
            f"📱 Тип: {type_label}\n"
            f"📦 Количество: {len(purchased_accounts)} шт" + (f" ({failed} не удалось)" if failed else "") + "\n"
            f"💰 Сумма: {int(actual_total)}₽\n"
            f"💸 Себестоимость LZT: {int(total_lzt_cost)}₽\n"
            f"📈 Прибыль: {int(actual_total - total_lzt_cost)}₽"
        )
        await notify_admin_purchase(callback.bot, admin_text)
        user_lzt_cart.pop(user_id, None)
        result_text = (
            f"✅ <b>Покупка успешна!</b>" + (f"\n⚠️ {failed} акк. не удалось выкупить" if failed else "") + "\n"
            f"📂 Категория: {subcat_name}\n"
            f"Страна: {cart['country_name']}\n"
            f"Тип: {type_label}\n"
            f"Количество: {len(purchased_accounts)} шт\n"
            f"Цена: {int(actual_total)}₽\n"
            f"🛡 Гарантия: 24 часа\n\n"
            f"📦 Данные аккаунтов:\n"
        )
        for idx, acc in enumerate(purchased_accounts, 1):
            result_text += f" <b>Аккаунт {idx}:</b>\n <code>{acc}</code>\n\n"
        result_text += "Сохраните их — они больше не будут показаны."
        await safe_edit(callback, result_text, reply_markup=post_purchase_kb)


# ========== ПОКУПКА ИЗ НАЛИЧИЯ ==========

@router.callback_query(F.data.startswith("buy_account:"))
async def buy_account_handler(callback: CallbackQuery):
    account_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    async with _get_user_lock(user_id):
        account = get_account(account_id)
        if not account or account["status"] != "available":
            await safe_answer(callback, "❌ Аккаунт уже продан", show_alert=True)
            return
        user = get_user(user_id)
        if not user or user["balance"] < account["price"]:
            bal = user["balance"] if user else 0
            await safe_answer(callback, f"❌ Недостаточно средств. Баланс: {int(bal)}₽", show_alert=True)
            return
        rl = check_redis_rate_limit(user_id, "buy", max_count=5, window_seconds=60)
        if not rl["ok"]:
            await safe_answer(callback, f"⏱ Слишком много покупок. Подождите {rl['retry_after']} сек.", show_alert=True)
            return
        deduct = deduct_balance_only(user_id, account["price"])
        if not deduct["ok"]:
            await safe_answer(callback, f"❌ {deduct.get('error')}", show_alert=True)
            return
        update_account_status(account_id, "sold")
        add_purchase(user_id, account_id, account["price"], guarantee_hours=24, is_insured=False)
        add_log(user_id, "buy_account", f"account_id={account_id}, price={account['price']}")
        set_user_cooldown(user_id, USER_BUY_COOLDOWN)
        type_label = "саморег" if account["account_type"] == "samoreg" else "авторег"
        await safe_edit(callback,
            f"✅ <b>Покупка успешна!</b>\n"
            f"Страна: {account['country_name']}\n"
            f"Тип: {type_label}\n"
            f"Цена: {int(account['price'])}₽\n"
            f"🛡 Гарантия: 24 часа\n\n"
            f"📦 Данные аккаунта:\n"
            f" <code>{account['data']}</code>\n\n"
            f"Сохраните их — они больше не будут показаны.",
            reply_markup=post_purchase_kb
        )


# ========== ИЗБРАННОЕ ==========

@router.callback_query(F.data.startswith("add_fav:"))
async def add_favorite_handler(callback: CallbackQuery):
    parts = callback.data.split(":")
    country_code = parts[1]
    subcat_key = parts[2] if len(parts) > 2 else "telegram"
    text = "⭐ <b>Добавить в избранное</b>\nВыберите тип аккаунта:"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧑 Саморег", callback_data=f"fav_confirm:{country_code}:samoreg:{subcat_key}")],
        [InlineKeyboardButton(text="🤖 Авторег", callback_data=f"fav_confirm:{country_code}:autoreg:{subcat_key}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"select_country:{country_code}:{subcat_key}")],
    ])
    await safe_edit(callback, text, reply_markup=kb)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("fav_confirm:"))
async def fav_confirm(callback: CallbackQuery):
    parts = callback.data.split(":")
    country_code = parts[1]
    account_type = parts[2]
    subcat_key = parts[3] if len(parts) > 3 else "telegram"
    add_favorite(callback.from_user.id, country_code, account_type)
    name = get_country_name(country_code)
    flag = get_country_flag(country_code)
    type_label = "саморег" if account_type == "samoreg" else "авторег"
    await safe_answer(callback, f"✅ {flag} {name} ({type_label}) добавлено!", show_alert=True)
    await safe_edit(callback,
        f"✅ <b>Добавлено в избранное!</b>\n{flag} {name} — {type_label}",
        reply_markup=back_to_main_kb
    )


@router.callback_query(F.data == "my_favorites")
async def my_favorites(callback: CallbackQuery):
    favorites = get_favorites(callback.from_user.id)
    if not favorites:
        text = "⭐ <b>Избранное</b>\nУ вас пока нет избранных позиций."
        await safe_edit(callback, text, reply_markup=back_to_buy_kb)
        await safe_answer(callback)
        return
    text = "⭐ <b>Избранное</b>\nНажмите, чтобы перейти к покупке:\n"
    await safe_edit(callback, text, reply_markup=favorites_kb(favorites))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("remove_fav:"))
async def remove_favorite_handler(callback: CallbackQuery):
    parts = callback.data.split(":")
    country_code = parts[1]
    account_type = parts[2]
    subcat_key = parts[3] if len(parts) > 3 else "telegram"
    remove_favorite(callback.from_user.id, country_code, account_type)
    await safe_answer(callback, "✅ Удалено из избранного")
    await my_favorites(callback)


# ========== ФИЛЬТРЫ ==========

@router.callback_query(F.data == "buy_filters")
async def buy_filters(callback: CallbackQuery):
    user_filters[callback.from_user.id] = {}
    text = "⚙️ <b>Фильтры поиска</b>\nНастройте параметры и нажмите 🧳 Показать."
    await safe_edit(callback, text, reply_markup=filters_kb)
    await safe_answer(callback)


@router.callback_query(F.data == "apply_filters")
async def apply_filters(callback: CallbackQuery):
    from database import get_db
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM accounts WHERE status = 'available' ORDER BY price ASC LIMIT 20")
    rows = c.fetchall()
    if not rows:
        await safe_edit(callback, "❌ По вашему запросу ничего не найдено.", reply_markup=back_to_buy_kb)
        await safe_answer(callback)
        return
    text = "🧳 <b>Результаты поиска:</b>\n"
    for row in rows:
        row = dict(row)
        type_label = "саморег" if row["account_type"] == "samoreg" else "авторег"
        text += f"• {row['country_name']} — {type_label} — {int(row['price'])}₽\n"
    await safe_edit(callback, text, reply_markup=back_to_buy_kb)
    await safe_answer(callback)


@router.callback_query(F.data == "reset_filters")
async def reset_filters(callback: CallbackQuery):
    user_filters[callback.from_user.id] = {}
    await safe_answer(callback, "✅ Фильтры сброшены")
    await buy_filters(callback)


@router.callback_query(F.data == "bulk_order")
async def bulk_order(callback: CallbackQuery):
    await safe_answer(callback, "🛠 Оптовые заказы в разработке", show_alert=True)


@router.callback_query(F.data.startswith("search_country:"))
async def search_country(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    subcat_key = parts[1] if len(parts) > 1 else "telegram"
    await state.set_state(SearchState.waiting_country)
    await state.update_data(subcat_key=subcat_key)
    await callback.message.answer("🔍 <b>Поиск страны</b>\nВведите название страны:")
    await safe_answer(callback)


@router.message(SearchState.waiting_country, F.text)
async def handle_search_country(message: Message, state: FSMContext):
    query = message.text.strip().lower()
    data = await state.get_data()
    subcat_key = data.get("subcat_key", "telegram")
    await state.clear()
    results = []
    for code, (name, flag) in country_map.items():
        if query in name.lower() or query in code.lower() or query in flag:
            results.append((code, name, flag))
    if not results:
        await message.answer("❌ Страна не найдена.", reply_markup=back_to_countries_kb)
        return
    if len(results) == 1:
        code, name, flag = results[0]
        text = f"{flag} <b>{name}</b>\nВыберите тип аккаунта:"
        await message.answer(text, reply_markup=country_type_kb(code, subcat_key))
        return
    text = "🔍 <b>Найдено несколько стран:</b>\n"
    kb_buttons = []
    for code, name, flag in results:
        kb_buttons.append([InlineKeyboardButton(text=f"{flag} {name}", callback_data=f"select_country:{code}:{subcat_key}")])
    kb_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"buy_subcat:{subcat_key}")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery):
    from keyboards import main_menu_kb
    text = f"👋 Привет, <b>{callback.from_user.full_name}</b>!\nДобро пожаловать в магазин."
    await safe_edit(callback, text, reply_markup=main_menu_kb)
    await safe_answer(callback)


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await safe_answer(callback)
