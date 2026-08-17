from aiogram import Router, types, F
from tg_utils import safe_answer, safe_edit
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import (
    get_account, add_purchase, update_account_status, get_user, add_log, add_account,
    add_favorite, get_favorites, remove_favorite, purchase_account_tx,
    purchase_existing_account_tx, add_to_cart
)
from lzt_api import search_telegram_accounts, fast_buy, get_account_data_lzt, get_lzt_balance, cancel_buy, confirm_buy
from keyboards import (
    buy_main_kb, countries_kb, country_type_kb,
    filters_kb, back_to_main_kb, back_to_buy_kb, back_to_countries_kb,
    lzt_cart_kb, progress_kb, favorites_kb, account_card_kb, insurance_kb,
    post_purchase_kb
)
from config import ADMIN_CHAT_ID, TOPIC_PURCHASES, USER_BUY_COOLDOWN
from redis_client import is_purchases_paused
from redis_client import acquire_item_lock, release_item_lock, set_user_cooldown, is_user_cooldown
from tg_validator import validate_account
from database import add_balance

router = Router()

user_filters = {}
user_lzt_cart = {}
user_pending_item = {}  # для страховки: {user_id: {...item...}}

class SearchState(StatesGroup):
    waiting_country = State()

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
    "KE": ("Кения", "🇰🇪"), "ZA": ("ЮАР", "🇿🇦"),
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


def build_account_card(item: dict, base_price: float, country_code: str, account_type: str) -> str:
    """Красивая карточка товара с эмодзи-прогрессом и характеристиками."""
    name = get_country_name(country_code)
    flag = get_country_flag(country_code)
    type_label = "🧑 Саморег (физ)" if account_type == "samoreg" else "🤖 Авторег (вирт)"

    # Характеристики
    age = item.get("item_age_days")
    age_str = f"{age} дней" if age is not None else "неизвестно"
    avatar = "✅ Есть" if item.get("has_avatar") else "❌ Нет"
    reg = item.get("reg_date") or "неизвестно"
    contacts = item.get("contacts_count")
    contacts_str = f"{contacts}" if contacts is not None else "неизвестно"
    premium = "✅ Есть" if item.get("has_premium") else "❌ Нет"

    text = (
        f"{flag} <b>{name}</b> — {type_label}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 <b>Цена:</b> {int(base_price)}₽\n"
        f"\n"
        f"📊 <b>Характеристики:</b>\n"
        f"  ⏱ Возраст: {age_str}\n"
        f"  🖼 Аватарка: {avatar}\n"
        f"  📅 Регистрация: {reg}\n"
        f"  👥 Контакты: {contacts_str}\n"
        f"  ⭐ Премиум: {premium}\n"
        f"\n"
        f"🛡 <b>Гарантия:</b> 24 часа (или пожизненная со страховкой)\n"
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
    type_label = "саморег" if account_type == "samoreg" else "авторег"

    text = (
        f"{name}\n"
        f"Тип: {type_label}\n"
        f"💰 Ваша цена: {int(base_price)}₽/шт\n"
        f"Количество: {qty} шт\n"
    )
    if disc > 0:
        text += f"Скидка: {int(disc * 100)}% ({int(price_per)}₽/шт)\n"
    text += (
        f"\n📦 Доступно: <b>{available} шт</b>\n"
        f"Покупаем {qty} шт?"
    )
    return text


async def notify_admin_purchase(bot, text: str):
    if ADMIN_CHAT_ID:
        try:
            kwargs = {}
            if TOPIC_PURCHASES:
                kwargs["message_thread_id"] = TOPIC_PURCHASES
            await bot.send_message(ADMIN_CHAT_ID, text, parse_mode="HTML", **kwargs)
        except Exception:
            pass


@router.callback_query(F.data == "buy_menu")
async def buy_menu(callback: CallbackQuery):
    text = (
        "📋 <b>Покупка аккаунта</b>\n"
        "Выберите действие:\n"
        "• 🌍 Посмотреть страны — выбрать страну и тип аккаунта\n"
        "• ⚙️ Фильтр — расширенный поиск по параметрам\n"
        "• ⭐ Избранное — быстрый доступ к частым покупкам\n"
        "• 🛒 Корзина — товары в корзине\n"
        "• ⭐ Отзывы — отзывы покупателей"
    )
    await safe_edit(callback, text, reply_markup=buy_main_kb)
    await safe_answer(callback, )


@router.callback_query(F.data == "view_countries")
async def view_countries(callback: CallbackQuery):
    text = (
        "🌍 <b>Доступные страны</b>\n"
        "Выберите страну из списка ниже.\n"
        "Нажмите на страну, чтобы выбрать тип аккаунта."
    )
    await safe_edit(callback, text, reply_markup=countries_kb(page=0))
    await safe_answer(callback, )


@router.callback_query(F.data.startswith("country_page:"))
async def country_page(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    text = (
        "🌍 <b>Доступные страны</b>\n"
        "Выберите страну из списка ниже.\n"
        "Нажмите на страну, чтобы выбрать тип аккаунта."
    )
    await safe_edit(callback, text, reply_markup=countries_kb(page=page))
    await safe_answer(callback, )


@router.callback_query(F.data.startswith("select_country:"))
async def select_country(callback: CallbackQuery):
    country_code = callback.data.split(":")[1]
    name = get_country_name(country_code)
    flag = get_country_flag(country_code)

    text = (
        f"{flag} <b>{name}</b>\n"
        "Выберите тип аккаунта:\n"
        "• 🧑 <b>Саморег (физ)</b> — физические SIM-карты, живые регистрации\n"
        "• 🤖 <b>Авторег (вирт)</b> — виртуальные номера, автоматическая регистрация"
    )
    await safe_edit(callback, text, reply_markup=country_type_kb(country_code))
    await safe_answer(callback, )


@router.callback_query(F.data.startswith("select_type:"))
async def select_type(callback: CallbackQuery):
    # ВАЖНО: отвечаем на callback СРАЗУ — поиск по LZT занимает 3+ сек,
    # иначе Telegram выдаёт "query is too old" и пользователь видит Bot Error.
    await safe_answer(callback)

    parts = callback.data.split(":")
    country_code = parts[1]
    account_type = parts[2]

    name = get_country_name(country_code)
    flag = get_country_flag(country_code)
    type_label = "саморег" if account_type == "samoreg" else "авторег"

    await safe_edit(callback,
        f"⏳ <b>Загрузка карточек...</b>\n{progress_kb(0).inline_keyboard[0][0].text}",
        reply_markup=progress_kb(0)
    )

    lzt_result = await search_telegram_accounts(country=country_code, account_type=account_type)

    if isinstance(lzt_result, dict) and lzt_result.get("error") == "token_expired":
        text = (
            f"{flag} <b>{name}</b>\n"
            "⚠️ <b>Каталог временно недоступен</b>\n"
            "Ведутся технические работы. Попробуйте позже."
        )
        await safe_edit(callback, text, reply_markup=back_to_countries_kb)
        await safe_answer(callback, )
        return

    lzt_items = lzt_result if isinstance(lzt_result, list) else lzt_result.get("items", [])
    lzt_items, exact_match = _filter_by_type(lzt_items, account_type)

    if not lzt_items:
        text = (
            f"{flag} <b>{name}</b>\n"
            f"❌ Сейчас нет аккаунтов типа <b>{type_label}</b> для этой страны.\n"
            "Попробуйте выбрать другой тип или страну."
        )
        await safe_edit(callback, text, reply_markup=back_to_countries_kb)
        await safe_answer(callback, )
        return

    lzt_prices = [item["price"] for item in lzt_items]
    avg_lzt = sum(lzt_prices) / len(lzt_prices)
    base_price = round(avg_lzt * 2, 2)

    # Рекомендации: показываем топ-3
    top_items = lzt_items[:3]
    rec_text = "\n🎯 <b>Рекомендуем:</b>\n"
    for idx, item in enumerate(top_items, 1):
        age = item.get("item_age_days")
        age_str = f"{age}д" if age else "?"
        premium = "⭐" if item.get("has_premium") else ""
        rec_text += f"  {idx}. Аккаунт #{idx} — возраст {age_str} {premium}\n"

    # Показываем первую карточку
    first_item = lzt_items[0]
    card_text = build_account_card(first_item, base_price, country_code, account_type)

    full_text = card_text + rec_text + "\n👇 Выберите аккаунт или добавьте в корзину:"

    user_lzt_cart[callback.from_user.id] = {
        "country_code": country_code,
        "account_type": account_type,
        "country_name": flag + " " + name,
        "items": lzt_items,
        "qty": 1,
        "base_price": base_price,
        "exact_match": True,
    }

    kb = account_card_kb(first_item["item_id"], base_price, country_code, account_type)
    await safe_edit(callback, full_text, reply_markup=kb)
    await safe_answer(callback, )


@router.callback_query(F.data.startswith("cart_plus:"))
async def cart_plus(callback: CallbackQuery):
    parts = callback.data.split(":")
    country_code = parts[1]
    account_type = parts[2]

    cart = user_lzt_cart.get(callback.from_user.id)
    if not cart:
        await safe_answer(callback, "❌ Сессия истекла", show_alert=True)
        return

    if cart["qty"] < len(cart["items"]):
        cart["qty"] += 1

    text = build_cart_text(callback.from_user.id)
    kb = lzt_cart_kb(
        country_code, account_type, cart["qty"], len(cart["items"]),
        calculate_price(cart["qty"], cart["base_price"])
    )
    await safe_edit(callback, text, reply_markup=kb)
    await safe_answer(callback, )


@router.callback_query(F.data.startswith("cart_minus:"))
async def cart_minus(callback: CallbackQuery):
    parts = callback.data.split(":")
    country_code = parts[1]
    account_type = parts[2]

    cart = user_lzt_cart.get(callback.from_user.id)
    if not cart:
        await safe_answer(callback, "❌ Сессия истекла", show_alert=True)
        return

    if cart["qty"] > 1:
        cart["qty"] -= 1

    text = build_cart_text(callback.from_user.id)
    kb = lzt_cart_kb(
        country_code, account_type, cart["qty"], len(cart["items"]),
        calculate_price(cart["qty"], cart["base_price"])
    )
    await safe_edit(callback, text, reply_markup=kb)
    await safe_answer(callback, )


@router.callback_query(F.data.startswith("cart_remove:"))
async def cart_remove(callback: CallbackQuery):
    user_lzt_cart.pop(callback.from_user.id, None)
    await safe_edit(callback, 
        "❌ Аккаунт убран из корзины.",
        reply_markup=back_to_countries_kb
    )
    await safe_answer(callback, "✅ Убрано")


@router.callback_query(F.data.startswith("add_to_cart:"))
async def add_to_cart_handler(callback: CallbackQuery):
    """Добавление текущего лота в корзину пользователя."""
    item_id = int(callback.data.split(":")[1])
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
        await safe_answer(callback, "❌ Аккаунт не найден. Обновите карточку.", show_alert=True)
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
    add_log(user_id, "add_to_cart", f"item_id={item_id}, price={cart['base_price']}")
    await safe_answer(callback, 
        f"✅ Добавлено в корзину!\n{cart['country_name']} — {int(cart['base_price'])}₽",
        show_alert=True
    )


# ========== НОВЫЙ ПОТОК: ПРЕДЛОЖЕНИЕ СТРАХОВКИ ==========
@router.callback_query(F.data.startswith("pre_buy:"))
async def pre_buy_handler(callback: CallbackQuery):
    """Перед покупкой предлагаем страховку."""
    item_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    cart = user_lzt_cart.get(user_id)
    if not cart:
        await safe_answer(callback, "❌ Сессия истекла", show_alert=True)
        return

    # Находим item
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
    }

    base = cart["base_price"]
    insured = round(base * 1.2, 2)

    text = (
        f"🛡 <b>Выберите тип гарантии</b>\n\n"
        f"📦 Аккаунт: <b>{cart['country_name']}</b>\n"
        f"💰 Базовая цена: <b>{int(base)}₽</b>\n\n"
        f"1️⃣ <b>Стандарт</b> — {int(base)}₽\n"
        f"   ✅ Гарантия 24 часа\n"
        f"   ⚠️ После 24ч — без права на возврат\n\n"
        f"2️⃣ <b>Страховка (+20%)</b> — {int(insured)}₽\n"
        f"   🛡 <b>Пожизненная гарантия</b>\n"
        f"   ✅ Возврат или замена навсегда\n"
        f"   💎 Приоритет в поддержке\n\n"
        f"Выберите вариант:"
    )
    await safe_edit(callback, text, reply_markup=insurance_kb)
    await safe_answer(callback, )


@router.callback_query(F.data == "buy_insured")
async def buy_insured(callback: CallbackQuery):
    await _do_buy(callback, insured=True)


@router.callback_query(F.data == "buy_no_insurance")
async def buy_no_insurance(callback: CallbackQuery):
    await _do_buy(callback, insured=False)


async def _do_buy(callback: CallbackQuery, insured: bool):
    user_id = callback.from_user.id
    pending = user_pending_item.pop(user_id, None)
    if not pending:
        await safe_answer(callback, "❌ Сессия истекла", show_alert=True)
        return

    item = pending["item"]
    cart = pending["cart"]
    base_price = pending["base_price"]
    price = round(base_price * 1.2, 2) if insured else base_price

    if is_purchases_paused():
        await safe_answer(callback, 
            "🛑 Покупки временно приостановлены.\n"
            "Ведутся технические работы. Попробуйте позже.",
            show_alert=True
        )
        return

    user = get_user(user_id)
    if not user or user["balance"] < price:
        bal = user["balance"] if user else 0
        await safe_answer(callback,
            f"❌ Недостаточно средств. Баланс: {int(bal)}₽, нужно: {int(price)}₽",
            show_alert=True
        )
        return

    if is_user_cooldown(user_id):
        await safe_answer(callback,
            f"⏱ Подождите {USER_BUY_COOLDOWN} сек между покупками.",
            show_alert=True
        )
        return

    item_id = item["item_id"]
    lzt_price = item["price"]

    # Блокируем лот, чтобы два покупателя не зарезервировали один аккаунт
    if not acquire_item_lock(item_id, user_id):
        await safe_answer(callback,
            "⚠️ Этот аккаунт сейчас покупает другой пользователь.\n"
            "Выберите другой лот.",
            show_alert=True
        )
        return

    await safe_answer(callback, "⏳ Покупаем аккаунт...")
    await safe_edit(callback,
        "⏳ <b>Покупка аккаунта...</b>\n" + progress_kb(1).inline_keyboard[0][0].text,
        reply_markup=progress_kb(1)
    )

    buy_result = await fast_buy(item_id)
    if buy_result.get("error") or not buy_result.get("status"):
        release_item_lock(item_id)
        await safe_edit(callback,
            "❌ <b>Резервирование не удалось</b>\n"
            "Лот могли купить другие. Попробуйте позже.",
            reply_markup=back_to_main_kb
        )
        return

    await safe_edit(callback, 
        "⏳ <b>Получение данных...</b>\n" + progress_kb(2).inline_keyboard[0][0].text,
        reply_markup=progress_kb(2)
    )

    data_result = await get_account_data_lzt(item_id)
    if data_result.get("error"):
        await cancel_buy(item_id)
        release_item_lock(item_id)
        await safe_edit(callback,
            "❌ <b>Не удалось получить данные</b>\n"
            "Покупка отменена, деньги возвращены.",
            reply_markup=back_to_main_kb
        )
        return

    login = data_result.get("login", "N/A")
    password = data_result.get("password", "N/A")
    session = data_result.get("session", "N/A")
    has_2fa = data_result.get("2fa", False)

    if login == "N/A" or not session or session == "N/A":
        await cancel_buy(item_id)
        release_item_lock(item_id)
        await safe_edit(callback,
            "❌ <b>Данные аккаунта повреждены</b>\n"
            "Покупка отменена.",
            reply_markup=back_to_main_kb
        )
        return

    await safe_edit(callback,
        "⏳ <b>Проверка и выдача...</b>\n" + progress_kb(3).inline_keyboard[0][0].text,
        reply_markup=progress_kb(3)
    )

    confirm_result = await confirm_buy(item_id)
    if confirm_result.get("error"):
        await cancel_buy(item_id)
        release_item_lock(item_id)
        await safe_edit(callback,
            "❌ <b>Подтверждение покупки не удалось</b>",
            reply_markup=back_to_main_kb
        )
        return

    account_data = (
        f"Телефон: {login}\n"
        f"Пароль: {password}\n"
        f"Сессия: {session}"
    )
    if has_2fa:
        account_data += "\n⚠️ На аккаунте включен 2FA"

    # Атомарная транзакция
    result = purchase_account_tx(
        user_id=user_id,
        account_id=0,  # создастся новый
        price=price,
        cost_price=lzt_price,
        account_data=account_data,
        country_code=cart["country_code"],
        country_name=cart["country_name"],
        account_type=cart["account_type"],
        item_age_days=item.get("item_age_days"),
        has_avatar=item.get("has_avatar", False),
        reg_date=item.get("reg_date"),
        contacts_count=item.get("contacts_count"),
        has_premium=item.get("has_premium", False),
        guarantee_hours=24,
        is_insured=insured,
    )

    if not result["ok"]:
        await cancel_buy(item_id)
        release_item_lock(item_id)
        await safe_edit(callback,
            f"❌ <b>Ошибка покупки:</b> {result.get('error', 'unknown')}",
            reply_markup=back_to_main_kb
        )
        return

    guarantee_text = "🛡 Пожизненная гарантия" if insured else "🛡 Гарантия 24 часа"
    type_label = "саморег" if cart["account_type"] == "samoreg" else "авторег"

    admin_text = (
        f"🛒 <b>Новая покупка!</b>\n"
        f"👤 Пользователь: <code>{user_id}</code>\n"
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
        f"Страна: {cart['country_name']}\n"
        f"Тип: {type_label}\n"
        f"Цена: {int(price)}₽\n"
        f"{guarantee_text}\n\n"
        f"📦 Данные аккаунта:\n"
        f"<code>{account_data}</code>\n\n"
        f"💾 Сохраните их — они больше не будут показаны."
    )
    await safe_edit(callback, result_text, reply_markup=post_purchase_kb)
    set_user_cooldown(user_id, USER_BUY_COOLDOWN)


@router.callback_query(F.data.startswith("buy_lzt:"))
async def buy_lzt(callback: CallbackQuery):
    if is_purchases_paused():
        await safe_answer(callback, 
            "🛑 Покупки временно приостановлены.\n"
            "Ведутся технические работы. Попробуйте позже.",
            show_alert=True
        )
        return

    parts = callback.data.split(":")
    country_code = parts[1]
    account_type = parts[2]
    qty = int(parts[3])

    user_id = callback.from_user.id
    cart = user_lzt_cart.get(user_id)
    if not cart:
        await safe_answer(callback, "❌ Сессия истекла. Начните заново.", show_alert=True)
        return

    total_price = calculate_price(qty, cart["base_price"])
    user = get_user(user_id)
    if not user or user["balance"] < total_price:
        bal = user["balance"] if user else 0
        await safe_answer(callback,
            f"❌ Недостаточно средств. Баланс: {int(bal)}₽, нужно: {int(total_price)}₽",
            show_alert=True
        )
        return

    if is_user_cooldown(user_id):
        await safe_answer(callback,
            f"⏱ Подождите {USER_BUY_COOLDOWN} сек между покупками.",
            show_alert=True
        )
        return

    # Цена за штуку с учётом скидки за количество
    price_per = round(cart["base_price"] * (1 - discount_percent(qty)), 2)

    await safe_answer(callback, f"⏳ Покупаем {qty} аккаунт(ов)...")
    await safe_edit(callback, 
        "⏳ <b>Покупка аккаунтов...</b>\n" + progress_kb(1).inline_keyboard[0][0].text,
        reply_markup=progress_kb(1)
    )

    lzt_user = await get_lzt_balance()
    lzt_balance = 0.0
    if isinstance(lzt_user, dict) and "balance" in lzt_user:
        try:
            lzt_balance = float(lzt_user["balance"])
        except (ValueError, TypeError):
            lzt_balance = 0.0

    estimated_cost = sum(cart["items"][i]["price"] for i in range(min(qty, len(cart["items"]))))
    if lzt_balance < estimated_cost:
        await safe_edit(callback, 
            "⚠️ <b>Сервис временно недоступен</b>\n"
            "Попробуйте позже или обратитесь в поддержку.",
            reply_markup=back_to_main_kb
        )
        await safe_answer(callback, )
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
        used_item_ids.add(item_id)

        # Блокируем лот, чтобы его не купил другой пользователь параллельно
        if not acquire_item_lock(item_id, user_id):
            failed += 1
            continue

        buy_result = await fast_buy(item_id)
        if buy_result.get("error") or not buy_result.get("status"):
            release_item_lock(item_id)
            failed += 1
            continue

        data_result = await get_account_data_lzt(item_id)
        if data_result.get("error"):
            await cancel_buy(item_id)
            release_item_lock(item_id)
            failed += 1
            continue

        login = data_result.get("login", "N/A")
        password = data_result.get("password", "N/A")
        session = data_result.get("session", "N/A")
        has_2fa = data_result.get("2fa", False)

        if login == "N/A" or not session or session == "N/A":
            await cancel_buy(item_id)
            release_item_lock(item_id)
            failed += 1
            continue

        confirm_result = await confirm_buy(item_id)
        if confirm_result.get("error"):
            await cancel_buy(item_id)
            release_item_lock(item_id)
            failed += 1
            continue

        account_data = (
            f"Телефон: {login}\n"
            f"Пароль: {password}\n"
            f"Сессия: {session}"
        )
        if has_2fa:
            account_data += "\n⚠️ На аккаунте включен 2FA"

        # FIX: атомарная транзакция — списывает баланс, создаёт аккаунт и покупку.
        # Раньше здесь были add_account/update_account_status/add_purchase,
        # которые НЕ списывали баланс — аккаунты уходили бесплатно.
        tx = purchase_account_tx(
            user_id=user_id,
            account_id=0,
            price=price_per,
            cost_price=lzt_price,
            account_data=account_data,
            country_code=cart["country_code"],
            country_name=cart["country_name"],
            account_type=cart["account_type"],
            item_age_days=item.get("item_age_days"),
            has_avatar=item.get("has_avatar", False),
            reg_date=item.get("reg_date"),
            contacts_count=item.get("contacts_count"),
            has_premium=item.get("has_premium", False),
            guarantee_hours=24,
            is_insured=False,
        )
        if not tx["ok"]:
            await cancel_buy(item_id)
            release_item_lock(item_id)
            failed += 1
            continue

        purchased_accounts.append(account_data)
        total_lzt_cost += lzt_price

    if not purchased_accounts:
        await safe_edit(callback, 
            "❌ <b>Покупка не удалась</b>\n"
            "Не удалось выкупить аккаунты.\n"
            "Возможно, их уже купили другие. Попробуйте позже.",
            reply_markup=back_to_main_kb
        )
        await safe_answer(callback, )
        return

    successful_qty = len(purchased_accounts)
    # Фактически списано через purchase_account_tx: price_per × successful_qty
    actual_total = round(price_per * successful_qty, 2)

    set_user_cooldown(user_id, USER_BUY_COOLDOWN)
    add_log(user_id, "buy_lzt_bulk", f"qty={successful_qty}, total={actual_total}")

    type_label = "саморег" if cart["account_type"] == "samoreg" else "авторег"
    admin_text = (
        f"🛒 <b>Новая покупка!</b>\n"
        f"👤 Пользователь: <code>{user_id}</code>\n"
        f"🌍 Страна: {cart['country_name']}\n"
        f"📱 Тип: {type_label}\n"
        f"📦 Количество: {successful_qty} шт" + (f" ({failed} не удалось)" if failed else "") + "\n"
        f"💰 Сумма: {int(actual_total)}₽\n"
        f"💸 Себестоимость LZT: {int(total_lzt_cost)}₽\n"
        f"📈 Прибыль: {int(actual_total - total_lzt_cost)}₽"
    )
    await notify_admin_purchase(callback.bot, admin_text)

    user_lzt_cart.pop(user_id, None)

    result_text = (
        f"✅ <b>Покупка успешна!</b>" + (f"\n⚠️ {failed} акк. не удалось выкупить" if failed else "") + "\n"
        f"Страна: {cart['country_name']}\n"
        f"Тип: {type_label}\n"
        f"Количество: {successful_qty} шт\n"
        f"Цена: {int(actual_total)}₽\n"
        f"🛡 Гарантия: 24 часа\n\n"
        f"📦 Данные аккаунтов:\n"
    )
    for idx, acc in enumerate(purchased_accounts, 1):
        result_text += f"<b>Аккаунт {idx}:</b>\n<code>{acc}</code>\n\n"
    result_text += "Сохраните их — они больше не будут показаны."

    await safe_edit(callback, result_text, reply_markup=post_purchase_kb)
    await safe_answer(callback, )


@router.callback_query(F.data.startswith("buy_account:"))
async def buy_account_handler(callback: CallbackQuery):
    account_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    account = get_account(account_id)
    if not account or account["status"] != "available":
        await safe_answer(callback, "❌ Аккаунт уже продан или недоступен", show_alert=True)
        return

    user = get_user(user_id)
    if not user or user["balance"] < account["price"]:
        bal = user["balance"] if user else 0
        await safe_answer(callback, 
            f"❌ Недостаточно средств. Баланс: {int(bal)}₽, нужно: {int(account['price'])}₽",
            show_alert=True
        )
        return

    # FIX: атомарная транзакция — списывает баланс и помечает аккаунт проданным.
    # Раньше баланс не списывался (add_purchase + update_account_status).
    tx = purchase_existing_account_tx(user_id, account_id, account["price"],
                                      guarantee_hours=24, is_insured=False)
    if not tx["ok"]:
        error = tx.get("error", "unknown")
        if error == "insufficient_balance":
            await safe_answer(callback, "❌ Недостаточно средств на балансе", show_alert=True)
        elif error == "account_unavailable":
            await safe_answer(callback, "❌ Аккаунт уже продан", show_alert=True)
        else:
            await safe_answer(callback, f"❌ Ошибка покупки: {error}", show_alert=True)
        return

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
        f"<code>{account['data']}</code>\n\n"
        f"Сохраните их — они больше не будут показаны.",
        reply_markup=post_purchase_kb
    )


# ========== ИЗБРАННОЕ ==========
@router.callback_query(F.data.startswith("add_fav:"))
async def add_favorite_handler(callback: CallbackQuery):
    country_code = callback.data.split(":")[1]
    text = (
        "⭐ <b>Добавить в избранное</b>\n"
        "Выберите тип аккаунта:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧑 Саморег", callback_data=f"fav_confirm:{country_code}:samoreg")],
        [InlineKeyboardButton(text="🤖 Авторег", callback_data=f"fav_confirm:{country_code}:autoreg")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"select_country:{country_code}")],
    ])
    await safe_edit(callback, text, reply_markup=kb)
    await safe_answer(callback, )


@router.callback_query(F.data.startswith("fav_confirm:"))
async def fav_confirm(callback: CallbackQuery):
    parts = callback.data.split(":")
    country_code = parts[1]
    account_type = parts[2]

    add_favorite(callback.from_user.id, country_code, account_type)

    name = get_country_name(country_code)
    flag = get_country_flag(country_code)
    type_label = "саморег" if account_type == "samoreg" else "авторег"

    await safe_answer(callback, f"✅ {flag} {name} ({type_label}) добавлено в избранное!", show_alert=True)
    await safe_edit(callback, 
        f"✅ <b>Добавлено в избранное!</b>\n"
        f"{flag} {name} — {type_label}\n"
        f"Быстрый доступ через 📋 Покупка аккаунта → ⭐ Избранное",
        reply_markup=back_to_main_kb
    )


@router.callback_query(F.data == "my_favorites")
async def my_favorites(callback: CallbackQuery):
    favorites = get_favorites(callback.from_user.id)
    if not favorites:
        text = (
            "⭐ <b>Избранное</b>\n"
            "У вас пока нет избранных позиций.\n"
            "Добавляйте часто покупаемые страны прямо из каталога — "
            "кнопка ⭐ В избранное рядом с выбором типа аккаунта."
        )
        await safe_edit(callback, text, reply_markup=back_to_buy_kb)
        await safe_answer(callback, )
        return

    text = "⭐ <b>Избранное</b>\nНажмите, чтобы быстро перейти к покупке:\n"
    await safe_edit(callback, text, reply_markup=favorites_kb(favorites))
    await safe_answer(callback, )


@router.callback_query(F.data.startswith("remove_fav:"))
async def remove_favorite_handler(callback: CallbackQuery):
    parts = callback.data.split(":")
    country_code = parts[1]
    account_type = parts[2]
    remove_favorite(callback.from_user.id, country_code, account_type)
    await safe_answer(callback, "✅ Удалено из избранного")
    await my_favorites(callback)


@router.callback_query(F.data == "buy_filters")
async def buy_filters(callback: CallbackQuery):
    user_filters[callback.from_user.id] = {}
    text = (
        "⚙️ <b>Фильтры поиска</b>\n"
        "Настройте параметры и нажмите 🧳 Показать."
    )
    await safe_edit(callback, text, reply_markup=filters_kb)
    await safe_answer(callback, )


@router.callback_query(F.data == "apply_filters")
async def apply_filters(callback: CallbackQuery):
    from database import get_db
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM accounts WHERE status = 'available' ORDER BY price ASC LIMIT 20")
    rows = c.fetchall()
    conn.close()

    if not rows:
        await safe_edit(callback, 
            "❌ По вашему запросу ничего не найдено.",
            reply_markup=back_to_buy_kb
        )
        await safe_answer(callback, )
        return

    text = "🧳 <b>Результаты поиска:</b>\n"
    for row in rows:
        row = dict(row)
        type_label = "саморег" if row["account_type"] == "samoreg" else "авторег"
        text += f"• {row['country_name']} — {type_label} — {int(row['price'])}₽\n"

    await safe_edit(callback, text, reply_markup=back_to_buy_kb)
    await safe_answer(callback, )


@router.callback_query(F.data == "reset_filters")
async def reset_filters(callback: CallbackQuery):
    user_filters[callback.from_user.id] = {}
    await safe_answer(callback, "✅ Фильтры сброшены")
    await buy_filters(callback)


@router.callback_query(F.data == "bulk_order")
async def bulk_order(callback: CallbackQuery):
    await safe_answer(callback, "🛠 Оптовые заказы в разработке", show_alert=True)


@router.callback_query(F.data == "search_country")
async def search_country(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SearchState.waiting_country)
    await callback.message.answer(
        "🔍 <b>Поиск страны</b>\n"
        "Введите название страны (например: <i>Франция</i> или <i>US</i>):"
    )
    await safe_answer(callback, )


@router.message(SearchState.waiting_country, F.text)
async def handle_search_country(message: Message, state: FSMContext):
    query = message.text.strip().lower()
    await state.clear()

    results = []
    for code, (name, flag) in country_map.items():
        if query in name.lower() or query in code.lower() or query in flag:
            results.append((code, name, flag))

    if not results:
        await message.answer(
            "❌ Страна не найдена. Попробуйте ещё раз.",
            reply_markup=back_to_countries_kb
        )
        return

    if len(results) == 1:
        code, name, flag = results[0]
        text = (
            f"{flag} <b>{name}</b>\n"
            "Выберите тип аккаунта:\n"
            "• 🧑 <b>Саморег (физ)</b>\n"
            "• 🤖 <b>Авторег (вирт)</b>"
        )
        await message.answer(text, reply_markup=country_type_kb(code))
        return

    text = "🔍 <b>Найдено несколько стран:</b>\n"
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb_buttons = []
    for code, name, flag in results:
        kb_buttons.append([InlineKeyboardButton(text=f"{flag} {name}", callback_data=f"select_country:{code}")])
    kb_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="view_countries")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)

    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery):
    from keyboards import main_menu_kb
    text = (
        f"👋 Привет, <b>{callback.from_user.full_name}</b>!\n"
        "Добро пожаловать в магазин Telegram-аккаунтов.\n"
        "Выбирай нужный раздел ниже 👇"
    )
    await safe_edit(callback, text, reply_markup=main_menu_kb)
    await safe_answer(callback, )


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await safe_answer(callback, )


def _filter_by_type(items, account_type):
    if not account_type or not items:
        return items, True

    autoreg_kw = [
        "авторег", "autoreg", "virtual", "вирт", "виртуал", "виртуальный",
        "вирт номер", "виртуалка", "софт", "регер", "регистратор", "бот",
        "soft reg", "soft-reg"
    ]
    samoreg_kw = [
        "саморег", "samoreg", "physical", "физ", "физический", "физ сим",
        "живой", "ручной", "manual", "real sim", "sim card", "физика",
        "живая регистрация", "handmade"
    ]

    explicit_match = []

    for item in items:
        reg_type = (item.get("registration_type") or "").lower()
        origin = (item.get("origin") or "").lower()
        resale_origin = (item.get("resale_origin") or "").lower()

        # Фишинг и стиллер исключены всегда (включая перепроданные лоты)
        if origin in ("phishing", "stealer") or resale_origin in ("phishing", "stealer"):
            continue

        # Точное совпадение по происхождению из API (самый надёжный признак)
        if origin:
            if account_type == "autoreg" and origin == "autoreg":
                explicit_match.append(item)
            elif account_type == "samoreg" and origin in ("self_registration", "personal"):
                explicit_match.append(item)
            continue

        if reg_type:
            if account_type == "autoreg" and reg_type == "virtual":
                explicit_match.append(item)
            elif account_type == "samoreg" and reg_type == "manual":
                explicit_match.append(item)
            continue

        text = (str(item.get("title", "")) + " " + str(item.get("description", ""))).lower()
        has_autoreg = any(kw in text for kw in autoreg_kw)
        has_samoreg = any(kw in text for kw in samoreg_kw)

        if account_type == "autoreg":
            if has_autoreg and not has_samoreg:
                explicit_match.append(item)
        else:
            if has_samoreg and not has_autoreg:
                explicit_match.append(item)

    return explicit_match, True
