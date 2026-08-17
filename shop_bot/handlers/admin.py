from aiogram import Router, F
from tg_utils import safe_answer, safe_edit
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS, ADMIN_CHAT_ID, TOPIC_MONITORING
from redis_client import set_purchases_paused
from database import (
    add_account, update_account_status, get_stats, seed_demo_accounts,
    get_user, set_price, get_stats_period, get_ticket, update_ticket_status,
    get_open_tickets
)
from lzt_api import search_telegram_accounts, demo_search, demo_buy, demo_get_data
from keyboards import admin_kb, back_to_main_kb, admin_price_type_kb, admin_ticket_kb

router = Router()


class AdminReplyState(StatesGroup):
    waiting_reply = State()


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет доступа к админ-панели.")
        return
    kb = admin_kb(message.from_user.id, ADMIN_IDS)
    await message.answer("🔧 <b>Админ-панель</b>", reply_markup=kb)


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await safe_answer(callback, "❌ Нет доступа", show_alert=True)
        return
    stats = get_stats()
    text = (
        f"📊 <b>Статистика</b>\n"
        f"👥 Пользователей: {stats['total_users']}\n"
        f"📦 Аккаунтов в наличии: {stats['total_accounts']}\n"
        f"🛒 Покупок: {stats['total_purchases']}\n"
        f"💰 Выручка: {round(stats['revenue'], 2)} ₽"
    )
    await safe_edit(callback, text, reply_markup=admin_kb(callback.from_user.id, ADMIN_IDS))
    await safe_answer(callback, )


@router.callback_query(F.data == "add_demo_account")
async def add_demo_account(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await safe_answer(callback, "❌ Нет доступа", show_alert=True)
        return
    seed_demo_accounts()
    await safe_answer(callback, "✅ Демо-аккаунты добавлены/обновлены")
    await admin_stats(callback)


@router.callback_query(F.data == "sync_lzt")
async def sync_lzt(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await safe_answer(callback, "❌ Нет доступа", show_alert=True)
        return
    await safe_answer(callback, "🔄 Синхронизация с LZT запущена (демо)", show_alert=True)


@router.message(Command("add_demo"))
async def cmd_add_demo(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет доступа")
        return
    seed_demo_accounts()
    await message.answer("✅ Демо-аккаунты добавлены/обновлены")


# !цена
@router.message(F.text.startswith("!цена"))
async def cmd_set_price(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет доступа")
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer(
            "❌ Неверный формат.\n"
            "Пример: <code>!цена US 95</code>\n"
            "или: <code>!цена США 95</code>"
        )
        return

    country_input = parts[1].upper()
    try:
        price = float(parts[2])
    except ValueError:
        await message.answer("❌ Цена должна быть числом.")
        return

    country_names_map = {
        "США": "US", "КАЗАХСТАН": "KZ", "ИНДИЯ": "IN", "ИНДОНЕЗИЯ": "ID",
        "ФИЛИППИНЫ": "PH", "ВЬЕТНАМ": "VN", "БРАЗИЛИЯ": "BR", "АРГЕНТИНА": "AR",
        "ТУРЦИЯ": "TR", "РУМЫНИЯ": "RO", "ПОЛЬША": "PL", "ГЕРМАНИЯ": "DE",
        "ВЕЛИКОБРИТАНИЯ": "GB", "ИТАЛИЯ": "IT", "ИСПАНИЯ": "ES", "ФРАНЦИЯ": "FR",
        "НИДЕРЛАНДЫ": "NL", "ЧЕХИЯ": "CZ", "БОЛГАРИЯ": "BG", "МЕКСИКА": "MX",
        "ЧИЛИ": "CL", "ПЕРУ": "PE", "КОЛУМБИЯ": "CO", "ТАИЛАНД": "TH",
        "МАЛАЙЗИЯ": "MY", "ПАКИСТАН": "PK", "БАНГЛАДЕШ": "BD", "ЕГИПЕТ": "EG",
        "МАРОККО": "MA", "НИГЕРИЯ": "NG", "КЕНИЯ": "KE", "ЮАР": "ZA",
    }

    country_code = country_input if len(country_input) == 2 else country_names_map.get(country_input)

    if not country_code:
        await message.answer("❌ Страна не найдена. Используйте код (US) или название (США).")
        return

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

    await message.answer(
        f"🌍 <b>{name}</b> — установить цену <b>{int(price)}₽</b>\n"
        f"Выберите тип аккаунта:",
        reply_markup=admin_price_type_kb(country_code, price)
    )


@router.callback_query(F.data.startswith("admin_set_price:"))
async def admin_set_price_callback(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await safe_answer(callback, "❌ Нет доступа", show_alert=True)
        return

    parts = callback.data.split(":")
    country_code = parts[1]
    account_type = parts[2]
    price = float(parts[3])

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

    if account_type == "both":
        set_price(country_code, "samoreg", price)
        set_price(country_code, "autoreg", price)
        await safe_edit(callback, 
            f"✅ Цена для <b>{name}</b> установлена:\n"
            f"• 🧑 Саморег: <b>{int(price)}₽</b>\n"
            f"• 🤖 Авторег: <b>{int(price)}₽</b>"
        )
    else:
        set_price(country_code, account_type, price)
        label = "🧑 Саморег" if account_type == "samoreg" else "🤖 Авторег"
        await safe_edit(callback, 
            f"✅ Цена для <b>{name}</b> установлена:\n"
            f"• {label}: <b>{int(price)}₽</b>"
        )

    await safe_answer(callback, "✅ Цена установлена")


# !синк
@router.message(F.text.startswith("!синк"))
async def cmd_sync_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет доступа")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "❌ Укажите период.\n"
            "Примеры:\n"
            "<code>!синк день</code>\n"
            "<code>!синк неделя</code>\n"
            "<code>!синк месяц</code>"
        )
        return

    period = parts[1].lower()
    if period not in ("день", "неделя", "месяц"):
        await message.answer("❌ Неверный период. Используйте: день, неделя, месяц")
        return

    stats = get_stats_period(period)
    if not stats:
        await message.answer("❌ Ошибка получения статистики.")
        return

    text = (
        f"📊 <b>Статистика за {period}</b>\n"
        f"🛒 Аккаунтов куплено: <b>{stats['purchases']}</b>\n"
        f"💰 Выручка: <b>{round(stats['revenue'], 2)} ₽</b>\n"
        f"💸 Потрачено (себестоимость): <b>{round(stats['costs'], 2)} ₽</b>\n"
        f"📈 Прибыль: <b>{round(stats['profit'], 2)} ₽</b>"
    )
    await message.answer(text)


# !поиск
@router.message(F.text.startswith("!поиск"))
async def cmd_search_lzt(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет доступа")
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer(
            "❌ Неверный формат.\n"
            "Пример: <code>!поиск US 50</code>\n"
            "(страна, максимальная цена)"
        )
        return

    country_input = parts[1].upper()
    try:
        max_price = float(parts[2])
    except ValueError:
        await message.answer("❌ Цена должна быть числом.")
        return

    country_names_map = {
        "США": "US", "КАЗАХСТАН": "KZ", "ИНДИЯ": "IN", "ИНДОНЕЗИЯ": "ID",
        "ФИЛИППИНЫ": "PH", "ВЬЕТНАМ": "VN", "БРАЗИЛИЯ": "BR", "АРГЕНТИНА": "AR",
        "ТУРЦИЯ": "TR", "РУМЫНИЯ": "RO", "ПОЛЬША": "PL", "ГЕРМАНИЯ": "DE",
        "ВЕЛИКОБРИТАНИЯ": "GB", "ИТАЛИЯ": "IT", "ИСПАНИЯ": "ES", "ФРАНЦИЯ": "FR",
        "НИДЕРЛАНДЫ": "NL", "ЧЕХИЯ": "CZ", "БОЛГАРИЯ": "BG", "МЕКСИКА": "MX",
        "ЧИЛИ": "CL", "ПЕРУ": "PE", "КОЛУМБИЯ": "CO", "ТАИЛАНД": "TH",
        "МАЛАЙЗИЯ": "MY", "ПАКИСТАН": "PK", "БАНГЛАДЕШ": "BD", "ЕГИПЕТ": "EG",
        "МАРОККО": "MA", "НИГЕРИЯ": "NG", "КЕНИЯ": "KE", "ЮАР": "ZA",
    }

    country_code = country_input if len(country_input) == 2 else country_names_map.get(country_input)

    if not country_code:
        await message.answer("❌ Страна не найдена.")
        return

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

    await message.answer(
        f"🔍 Ищем на LZT.market...\n"
        f"Параметры:\n"
        f"• Страна: {name}\n"
        f"• Макс. цена: {int(max_price)}₽\n"
        f"• Тип: саморег / авторег\n"
        f"• Отлёжка: от 1 дня\n"
        f"• Спамблок: нет\n"
        f"• Пароль: нет\n"
        f"• Почта: не важно"
    )

    items = await search_telegram_accounts(country=country_code)
    if not items:
        items = demo_search(country_code, "samoreg")
        items += demo_search(country_code, "autoreg")

    filtered = []
    for item in items:
        price = float(item.get("price", item.get("price_value", 999)))
        if price <= max_price:
            filtered.append(item)

    if not filtered:
        await message.answer(
            "❌ По заданным параметрам ничего не найдено.\n"
            "Попробуйте увеличить максимальную цену."
        )
        return

    text = (
        f"✅ <b>Найдено {len(filtered)} аккаунтов</b>\n"
        f"🌍 Страна: {name}\n"
        f"💰 Макс. цена: {int(max_price)}₽\n\n"
        f"📋 Результаты:\n"
    )

    for idx, item in enumerate(filtered[:10], 1):
        price = float(item.get("price", item.get("price_value", 0)))
        item_id = item.get("item_id", item.get("id", "N/A"))
        text += f"{idx}. ID: <code>{item_id}</code>\n"

    if len(filtered) > 10:
        text += f"\n...и ещё {len(filtered) - 10} шт."

    await message.answer(text)


# TEST BUY
@router.message(Command("test_buy"))
async def cmd_test_buy(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет доступа")
        return

    args = message.text.split()
    country_code = args[1].upper() if len(args) > 1 else "US"
    account_type = args[2] if len(args) > 2 else "samoreg"

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
    type_label = "саморег" if account_type == "samoreg" else "авторег"

    await message.answer(
        f"🧪 <b>ТЕСТОВАЯ ПОКУПКА</b>\n"
        f"Имитация полного цикла закупки с LZT.market...\n"
        f"⏳ Шаг 1/4: Поиск аккаунта на LZT..."
    )

    items = demo_search(country_code, account_type)
    item = items[0]
    item_id = item["item_id"]
    lzt_price = item["price"]
    sell_price = round(lzt_price * 1.3, 2)

    await message.answer(
        f"✅ Шаг 1/4: Аккаунт найден!\n"
        f"• ID: <code>{item_id}</code>\n"
        f"• Страна: 🇺🇸 {name}\n"
        f"• Тип: {type_label}\n"
        f"• Цена продажи: {int(sell_price)}₽\n\n"
        f"⏳ Шаг 2/4: Покупка на LZT..."
    )

    buy_result = demo_buy(item_id)

    await message.answer(
        f"✅ Шаг 2/4: Аккаунт выкуплен!\n"
        f"• Статус: {buy_result.get('status', 'ok')}\n"
        f"• Списано с баланса LZT: {int(lzt_price)}₽\n\n"
        f"⏳ Шаг 3/4: Получение данных..."
    )

    data = demo_get_data(item_id)

    login = data.get("login", "N/A")
    password = data.get("password", "N/A")
    session = data.get("session", "N/A")
    has_2fa = data.get("2fa", False)

    account_data = (
        f"Телефон: {login}\n"
        f"Пароль: {password}\n"
        f"Сессия: {session}"
    )
    if has_2fa:
        account_data += "\n⚠️ На аккаунте включен 2FA"

    acc_id = add_account(
        country_code=country_code,
        country_name="🇺🇸 " + name,
        account_type=account_type,
        price=sell_price,
        cost_price=lzt_price,
        data=account_data
    )
    update_account_status(acc_id, "sold")

    await message.answer(
        f"✅ Шаг 3/4: Данные получены!\n\n"
        f"⏳ Шаг 4/4: Сохранение в базу..."
    )

    await message.answer(
        f"✅ <b>ТЕСТОВАЯ ПОКУПКА ЗАВЕРШЕНА!</b>\n\n"
        f"📦 Результат:\n"
        f"• Страна: 🇺🇸 {name}\n"
        f"• Тип: {type_label}\n"
        f"• Цена продажи: {int(sell_price)}₽\n"
        f"• Прибыль: {int(sell_price - lzt_price)}₽\n\n"
        f"📋 Данные аккаунта:\n"
        f"<code>{account_data}</code>\n\n"
        f"✅ Аккаунт сохранён в базу как проданный (ID: {acc_id})"
    )


@router.callback_query(F.data == "resume_sales")
async def resume_sales(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await safe_answer(callback, "❌ Нет доступа", show_alert=True)
        return
    set_purchases_paused(False)
    await safe_edit(callback, 
        f"✅ <b>Продажи возобновлены вручную</b>\n"
        f"Бот снова принимает заказы.",
        reply_markup=admin_kb(callback.from_user.id, ADMIN_IDS)
    )
    await safe_answer(callback, "✅ Продажи возобновлены")


# TICKETS
@router.callback_query(F.data.startswith("admin_reply_ticket:"))
async def admin_reply_ticket(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await safe_answer(callback, "❌ Нет доступа", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[1])
    ticket = get_ticket(ticket_id)
    if not ticket:
        await safe_answer(callback, "❌ Тикет не найден", show_alert=True)
        return

    await state.update_data(reply_ticket_id=ticket_id, reply_user_id=ticket["user_id"])
    await callback.message.answer(
        f"🎫 <b>Ответ на тикет #{ticket_id}</b>\n"
        f"👤 Пользователь: <code>{ticket['user_id']}</code>\n"
        f"💬 Вопрос: {ticket['message'][:300]}...\n\n"
        f"Введите ответ для пользователя:"
    )
    await state.set_state(AdminReplyState.waiting_reply)
    await safe_answer(callback, )


@router.message(AdminReplyState.waiting_reply, F.text)
async def admin_send_reply(message: Message, state: FSMContext):
    data = await state.get_data()
    ticket_id = data.get("reply_ticket_id")
    user_id = data.get("reply_user_id")

    if not ticket_id or not user_id:
        await message.answer("❌ Ошибка: данные тикета потеряны.")
        await state.clear()
        return

    reply_text = message.text.strip()
    update_ticket_status(ticket_id, "closed", admin_reply=reply_text)

    try:
        await message.bot.send_message(
            user_id,
            f"✅ <b>Ответ на тикет #{ticket_id}</b>\n"
            f"👨‍💼 <b>Поддержка:</b>\n"
            f"<blockquote>{reply_text}</blockquote>\n\n"
            f"Если вопрос не решён — создайте новый тикет.",
            parse_mode="HTML"
        )
        await message.answer(f"✅ Ответ на тикет #{ticket_id} отправлен пользователю.")
    except Exception as e:
        await message.answer(f"⚠️ Не удалось отправить ответ пользователю: {e}")

    await state.clear()


@router.callback_query(F.data.startswith("admin_close_ticket:"))
async def admin_close_ticket(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await safe_answer(callback, "❌ Нет доступа", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[1])
    ticket = get_ticket(ticket_id)
    if not ticket:
        await safe_answer(callback, "❌ Тикет не найден", show_alert=True)
        return

    update_ticket_status(ticket_id, "closed", admin_reply="Тикет закрыт администратором.")

    try:
        await callback.bot.send_message(
            ticket["user_id"],
            f"🔴 <b>Тикет #{ticket_id} закрыт</b>\n"
            f"Ваше обращение закрыто администратором.\n"
            f"Если вопрос не решён — создайте новый тикет.",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await safe_answer(callback, f"✅ Тикет #{ticket_id} закрыт")
    await safe_edit(callback, 
        f"{callback.message.text}\n\n🔴 <b>ТИКЕТ ЗАКРЫТ</b>",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("admin_wait_ticket:"))
async def admin_wait_ticket(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await safe_answer(callback, "❌ Нет доступа", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[1])
    ticket = get_ticket(ticket_id)
    if not ticket:
        await safe_answer(callback, "❌ Тикет не найден", show_alert=True)
        return

    update_ticket_status(ticket_id, "waiting")

    try:
        await callback.bot.send_message(
            ticket["user_id"],
            f"🟡 <b>Тикет #{ticket_id} в обработке</b>\n"
            f"Ваше обращение передано на рассмотрение.\n"
            f"Мы ответим в ближайшее время.",
            parse_mode="HTML"
        )
    except Exception:
        pass

    await safe_answer(callback, f"⏳ Тикет #{ticket_id} переведён в ожидание")
    await safe_edit(callback, 
        f"{callback.message.text}\n\n🟡 <b>В ОЖИДАНИИ</b>",
        parse_mode="HTML"
    )


# !тикеты
@router.message(F.text.startswith("!тикеты"))
async def cmd_tickets(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет доступа")
        return

    tickets = get_open_tickets()
    if not tickets:
        await message.answer("🎫 Нет открытых тикетов.")
        return

    text = f"🎫 <b>Открытые тикеты ({len(tickets)}):</b>\n"
    for t in tickets[:20]:
        status_emoji = {"open": "🟢", "waiting": "🟡"}
        text += (
            f"{status_emoji.get(t['status'], '⚪')} <b>#{t['id']}</b> — "
            f"{t['type']} — <code>{t['user_id']}</code>\n"
        )

    await message.answer(text)
