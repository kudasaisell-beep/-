from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from tg_utils import safe_answer, safe_edit, send_safe_message
from database import (
    get_stats, get_stats_period, add_account, get_all_prices, set_price,
    get_user, get_recent_errors, get_open_tickets, get_ticket, update_ticket_status,
    create_ticket, get_pending_code_requests, update_code_request_status,
    get_user_purchases, get_pending_refunds, process_refund,
    get_deposit, update_deposit_status, add_balance
)
from keyboards import admin_kb, admin_price_type_kb, admin_ticket_kb, back_to_main_kb, admin_deposit_kb
from config import ADMIN_IDS, ADMIN_CHAT_ID
import logging

router = Router()

class AdminPriceState(StatesGroup):
    waiting_price = State()

class AdminReplyState(StatesGroup):
    waiting_reply = State()

class AdminSearchState(StatesGroup):
    waiting_query = State()

class AdminTicketSearchState(StatesGroup):
    waiting_query = State()

# FIX 30: decorator for admin checks
from functools import wraps

def admin_only(handler):
    @wraps(handler)
    async def wrapper(callback: CallbackQuery, *args, **kwargs):
        if callback.from_user.id not in ADMIN_IDS:
            await safe_answer(callback, "❌ Нет доступа", show_alert=True)
            return
        return await handler(callback, *args, **kwargs)
    return wrapper

def _parse_int_safe(s: str, min_val: int = None, max_val: int = None) -> int | None:
    try:
        v = int(s)
        if min_val is not None and v < min_val:
            return None
        if max_val is not None and v > max_val:
            return None
        return v
    except (ValueError, TypeError):
        return None

def _parse_float_safe(s: str, min_val: float = None, max_val: float = None) -> float | None:
    try:
        v = float(s)
        if min_val is not None and v < min_val:
            return None
        if max_val is not None and v > max_val:
            return None
        return v
    except (ValueError, TypeError):
        return None


# ========== АДМИН-КОМАНДЫ ==========

@router.message(F.text.startswith("!"))
async def admin_commands(message: Message):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        return
    text = message.text.strip()
    parts = text.split()
    command = parts[0].lower()

    if command == "!статистика":
        stats = get_stats()
        period = parts[1] if len(parts) > 1 else "день"
        if period not in ("день", "неделя", "месяц"):
            period = "день"
        period_stats = get_stats_period(period)
        msg = (
            f"📊 <b>Статистика</b>\n"
            f"Пользователей: {stats['total_users']}\n"
            f"Аккаунтов: {stats['total_accounts']}\n"
            f"Покупок: {stats['total_purchases']}\n"
            f"Доход: {int(stats['revenue'])}₽\n\n"
            f"📈 <b>За {period}:</b>\n"
            f"Покупок: {period_stats['purchases']}\n"
            f"Доход: {int(period_stats['revenue'])}₽\n"
            f"Себестоимость: {int(period_stats['costs'])}₽\n"
            f"Прибыль: {int(period_stats['profit'])}₽"
        )
        await message.answer(msg)

    elif command == "!цена":
        if len(parts) < 3:
            await message.answer("Использование: !цена КОД_СТРАНЫ ЦЕНА")
            return
        country_code = parts[1].upper()
        price = _parse_float_safe(parts[2], min_val=1, max_val=10000)
        if price is None:
            await message.answer("❌ Неверная цена")
            return
        await message.answer(f"💰 Установить цену для {country_code}?",
                             reply_markup=admin_price_type_kb(country_code, price))

    elif command == "!поиск":
        if len(parts) < 2:
            await message.answer("Использование: !поиск КОД_СТРАНЫ")
            return
        country_code = parts[1].upper()
        await message.answer(f"🔍 Результаты для {country_code}:")

    elif command == "!ошибки":
        errors = get_recent_errors()
        if not errors:
            await message.answer("✅ Нет недавних ошибок.")
            return
        msg = "🚨 <b>Последние ошибки:</b>\n"
        for i, err in enumerate(errors[:10], 1):
            msg += f"{i}. {str(err)[:200]}\n"
        await message.answer(msg)

    elif command == "!тикеты":
        tickets = get_open_tickets()
        if not tickets:
            await message.answer("✅ Нет открытых тикетов.")
            return
        msg = f"📋 <b>Открытые тикеты ({len(tickets)}):</b>\n"
        for t in tickets:
            msg += f"#{t['id']} — {t['type']} — {t['username']}\n"
        await message.answer(msg)

    elif command == "!пользователь":
        if len(parts) < 2:
            await message.answer("Использование: !пользователь USER_ID")
            return
        uid = _parse_int_safe(parts[1])
        if uid is None:
            await message.answer("❌ Неверный ID")
            return
        user = get_user(uid)
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        msg = (
            f"👤 <b>Пользователь {uid}</b>\n"
            f"Username: @{user.get('username', 'нет')}\n"
            f"Баланс: {int(user['balance'])}₽\n"
            f"Потрачено: {int(user['total_spent'])}₽\n"
            f"Рефералов: {user['referrals']}"
        )
        await message.answer(msg)

    elif command == "!коды":
        requests = get_pending_code_requests()
        if not requests:
            await message.answer("✅ Нет запросов на коды.")
            return
        msg = f"🔑 <b>Запросы на коды ({len(requests)}):</b>\n"
        for req in requests:
            msg += f"#{req['id']} — User: {req['user_id']} — Purchase: {req['purchase_id']}\n"
        await message.answer(msg)

    elif command == "!возвраты":
        refunds = get_pending_refunds()
        if not refunds:
            await message.answer("✅ Нет ожидающих возвратов.")
            return
        msg = f"💸 <b>Возвраты ({len(refunds)}):</b>\n"
        for r in refunds:
            msg += f"#{r['id']} — User: {r['user_id']} — {int(r['amount'])}₽ — {r['reason'][:50]}\n"
        await message.answer(msg)

    elif command.startswith("!возврат"):
        if len(parts) < 2:
            await message.answer("Использование: !возврат REFUND_ID")
            return
        rid = _parse_int_safe(parts[1])
        if rid is None:
            await message.answer("❌ Неверный ID возврата")
            return
        result = process_refund(rid)
        if result["ok"]:
            await message.answer(f"✅ Возврат #{rid} выполнен")
        else:
            await message.answer(f"❌ Ошибка: {result['error']}")

    else:
        await message.answer("❌ Неизвестная команда. Доступные: !статистика, !цена, !поиск, !ошибки, !тикеты, !пользователь, !коды, !возвраты, !возврат")


# ========== CALLBACK ХЕНДЛЕРЫ ==========

@router.callback_query(F.data == "admin_stats")
@admin_only
async def admin_stats(callback: CallbackQuery):
    stats = get_stats()
    period_stats = get_stats_period("день")
    msg = (
        f"📊 <b>Статистика</b>\n"
        f"Пользователей: {stats['total_users']}\n"
        f"Аккаунтов: {stats['total_accounts']}\n"
        f"Покупок: {stats['total_purchases']}\n"
        f"Доход: {int(stats['revenue'])}₽\n\n"
        f"📈 <b>За день:</b>\n"
        f"Покупок: {period_stats['purchases']}\n"
        f"Доход: {int(period_stats['revenue'])}₽\n"
        f"Себестоимость: {int(period_stats['costs'])}₽\n"
        f"Прибыль: {int(period_stats['profit'])}₽"
    )
    await safe_edit(callback, msg, reply_markup=admin_kb(callback.from_user.id, ADMIN_IDS))
    await safe_answer(callback)


@router.callback_query(F.data == "add_demo_account")
@admin_only
async def add_demo_account(callback: CallbackQuery):
    countries = [
        ("US", "США", "🇺🇸", 45, 95), ("KZ", "Казахстан", "🇰🇿", 35, 75),
        ("IN", "Индия", "🇮🇳", 25, 55), ("ID", "Индонезия", "🇮🇩", 30, 65),
        ("PH", "Филиппины", "🇵🇭", 28, 60), ("VN", "Вьетнам", "🇻🇳", 32, 70),
        ("BR", "Бразилия", "🇧🇷", 40, 85), ("AR", "Аргентина", "🇦🇷", 38, 80),
        ("TR", "Турция", "🇹🇷", 42, 88), ("RO", "Румыния", "🇷🇴", 36, 78),
        ("PL", "Польша", "🇵🇱", 44, 92), ("DE", "Германия", "🇩🇪", 55, 120),
    ]
    for code, name, flag, p1, p2 in countries:
        for i in range(3):
            add_account(code, flag + " " + name, "samoreg", p1 + i * 5, p1 * 0.6,
                f"demo_{code}_samoreg_{i}", 30 + i * 5, True, "2024-01-10", 5 + i, False)
            add_account(code, flag + " " + name, "autoreg", p2 + i * 10, p2 * 0.6,
                f"demo_{code}_autoreg_{i}", 60 + i * 10, True, "2023-06-05", 0, True)
    await safe_answer(callback, "✅ Демо-аккаунты добавлены")
    await safe_edit(callback, "✅ <b>Демо-аккаунты добавлены!</b>", reply_markup=admin_kb(callback.from_user.id, ADMIN_IDS))


@router.callback_query(F.data == "sync_lzt")
@admin_only
async def sync_lzt(callback: CallbackQuery):
    await safe_answer(callback, "🔄 Синхронизация с LZT...")
    await safe_edit(callback, "🔄 <b>Синхронизация с LZT</b>\nИмпорт аккаунтов...", reply_markup=admin_kb(callback.from_user.id, ADMIN_IDS))


@router.callback_query(F.data.startswith("admin_set_price:"))
@admin_only
async def admin_set_price(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 4:
        await safe_answer(callback, "❌ Неверные данные", show_alert=True)
        return
    country_code = parts[1].upper()
    account_type = parts[2]
    price = _parse_float_safe(parts[3], min_val=1, max_val=10000)
    if price is None:
        await safe_answer(callback, "❌ Неверная цена", show_alert=True)
        return
    if account_type == "both":
        set_price(country_code, "samoreg", price)
        set_price(country_code, "autoreg", price)
    else:
        set_price(country_code, account_type, price)
    await safe_answer(callback, f"✅ Цена для {country_code} установлена: {int(price)}₽")
    await safe_edit(callback, f"✅ <b>Цена обновлена!</b>\n{country_code} — {int(price)}₽", reply_markup=admin_kb(callback.from_user.id, ADMIN_IDS))


# ========== ТИКЕТЫ ==========

@router.callback_query(F.data.startswith("admin_reply_ticket:"))
@admin_only
async def admin_reply_ticket(callback: CallbackQuery, state: FSMContext):
    ticket_id = _parse_int_safe(callback.data.split(":")[1], min_val=1)
    if ticket_id is None:
        await safe_answer(callback, "❌ Неверный ID тикета", show_alert=True)
        return
    ticket = get_ticket(ticket_id)
    if not ticket:
        await safe_answer(callback, "❌ Тикет не найден", show_alert=True)
        return
    if ticket["status"] == "closed":
        await safe_answer(callback, "❌ Тикет уже закрыт", show_alert=True)
        return
    await state.set_state(AdminReplyState.waiting_reply)
    await state.update_data(ticket_id=ticket_id)
    await safe_answer(callback, "✏️ Введите ответ:")
    await callback.message.answer(f"🎫 <b>Тикет #{ticket_id}</b>\nСтатус: {ticket['status']}\n\nВведите ваш ответ:")


@router.message(AdminReplyState.waiting_reply, F.text)
async def admin_send_reply(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет доступа")
        await state.clear()
        return
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    if not ticket_id:
        await message.answer("❌ Ошибка: тикет не найден в сессии")
        await state.clear()
        return
    ticket = get_ticket(ticket_id)
    if not ticket:
        await message.answer("❌ Тикет не найден")
        await state.clear()
        return
    if ticket["status"] == "closed":
        await message.answer("❌ Тикет уже закрыт")
        await state.clear()
        return
    reply_text = message.text.strip()
    if not reply_text:
        await message.answer("❌ Ответ не может быть пустым")
        return
    update_ticket_status(ticket_id, "closed", reply_text)
    await message.answer(f"✅ Ответ отправлен! Тикет #{ticket_id} закрыт.")
    try:
        await send_safe_message(message.bot,
            f"📨 <b>Ответ от поддержки</b>\n\n{reply_text}\n\n✅ Тикет #{ticket_id} закрыт.",
            chat_id=ticket["user_id"])
    except Exception as e:
        logging.error(f"Failed to notify user about ticket reply: {e}")
    await state.clear()


@router.callback_query(F.data.startswith("admin_close_ticket:"))
@admin_only
async def admin_close_ticket(callback: CallbackQuery):
    ticket_id = _parse_int_safe(callback.data.split(":")[1], min_val=1)
    if ticket_id is None:
        await safe_answer(callback, "❌ Неверный ID", show_alert=True)
        return
    ticket = get_ticket(ticket_id)
    if not ticket:
        await safe_answer(callback, "❌ Тикет не найден", show_alert=True)
        return
    update_ticket_status(ticket_id, "closed")
    await safe_answer(callback, f"✅ Тикет #{ticket_id} закрыт")
    try:
        await send_safe_message(callback.bot, f"✅ Тикет #{ticket_id} закрыт администратором.", chat_id=ticket["user_id"])
    except Exception:
        pass


@router.callback_query(F.data.startswith("admin_wait_ticket:"))
@admin_only
async def admin_wait_ticket(callback: CallbackQuery):
    ticket_id = _parse_int_safe(callback.data.split(":")[1], min_val=1)
    if ticket_id is None:
        await safe_answer(callback, "❌ Неверный ID", show_alert=True)
        return
    update_ticket_status(ticket_id, "waiting")
    await safe_answer(callback, f"⏳ Тикет #{ticket_id} в ожидании")


# ========== ОБРАБОТКА ПОПОЛНЕНИЙ ==========

@router.callback_query(F.data.startswith("admin_deposit_accept:"))
@admin_only
async def admin_deposit_accept(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) < 4:
        await safe_answer(callback, "❌ Неверные данные", show_alert=True)
        return
    deposit_id = _parse_int_safe(parts[1])
    user_id = _parse_int_safe(parts[2])
    amount = _parse_float_safe(parts[3])
    if not all([deposit_id, user_id, amount]):
        await safe_answer(callback, "❌ Неверные параметры", show_alert=True)
        return

    deposit = get_deposit(deposit_id)
    if not deposit or deposit["status"] != "pending":
        await safe_answer(callback, "❌ Заявка уже обработана", show_alert=True)
        return

    # Начисляем баланс
    add_balance(user_id, amount)
    update_deposit_status(deposit_id, "accepted")

    await safe_answer(callback, f"✅ Зачислено {int(amount)}₽ пользователю {user_id}")
    await safe_edit(callback, f"✅ <b>Пополнение принято</b>\nПользователь: <code>{user_id}</code>\nСумма: {int(amount)}₽")

    # Уведомляем пользователя
    try:
        await send_safe_message(callback.bot,
            f"✅ <b>Пополнение зачислено!</b>\n\n"
            f"Сумма: <b>{int(amount)}₽</b>\n"
            f"Баланс обновлён. Приятных покупок! 🛒",
            chat_id=user_id)
    except Exception as e:
        logging.error(f"Failed to notify user about deposit: {e}")


@router.callback_query(F.data.startswith("admin_deposit_reject:"))
@admin_only
async def admin_deposit_reject(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) < 3:
        await safe_answer(callback, "❌ Неверные данные", show_alert=True)
        return
    deposit_id = _parse_int_safe(parts[1])
    user_id = _parse_int_safe(parts[2])
    if not all([deposit_id, user_id]):
        await safe_answer(callback, "❌ Неверные параметры", show_alert=True)
        return

    deposit = get_deposit(deposit_id)
    if not deposit or deposit["status"] != "pending":
        await safe_answer(callback, "❌ Заявка уже обработана", show_alert=True)
        return

    update_deposit_status(deposit_id, "rejected")

    await safe_answer(callback, f"❌ Пополнение отклонено")
    await safe_edit(callback, f"❌ <b>Пополнение отклонено</b>\nПользователь: <code>{user_id}</code>")

    # Уведомляем пользователя
    try:
        await send_safe_message(callback.bot,
            f"❌ <b>Пополнение отклонено</b>\n\n"
            f"Админ отклонил вашу заявку на пополнение.\n"
            f"Если вы уверены, что перевод был выполнен — создайте тикет в поддержке.",
            chat_id=user_id)
    except Exception as e:
        logging.error(f"Failed to notify user about rejected deposit: {e}")


# ========== СДЕЛКИ LZT ==========

@router.callback_query(F.data.startswith("admin_buy_deal:"))
@admin_only
async def admin_buy_deal(callback: CallbackQuery):
    parts = callback.data.split(":")
    country_code = parts[1].upper()
    account_type = parts[2]
    price = _parse_int_safe(parts[3])
    await safe_answer(callback, f"🛒 Закупка {country_code} {account_type} за {price}₽...")


@router.callback_query(F.data == "admin_skip_deal")
@admin_only
async def admin_skip_deal(callback: CallbackQuery):
    await safe_answer(callback, "⏭ Пропущено")
