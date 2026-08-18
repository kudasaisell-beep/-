from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from tg_utils import safe_answer, safe_edit, send_safe_message
from database import (
    create_ticket, get_user_tickets, get_ticket, get_user_purchases
)
from keyboards import support_menu_kb, faq_kb, ticket_type_kb, back_to_support_kb, back_to_main_kb

router = Router()

class TicketState(StatesGroup):
    waiting_message = State()

TICKET_MAX_LEN = 3000  # FIX 14: ограничение длины сообщения

@router.callback_query(F.data == "support_menu")
async def support_menu(callback: CallbackQuery):
    text = (
        "📞 **Поддержка**\n"
        "Выберите действие:\n"
        "• ❓ FAQ — частые вопросы\n"
        "• 📦 Как купить — инструкция\n"
        "• 🎫 Создать тикет — написать в поддержку\n"
        "• 📋 Мои тикеты — история обращений"
    )
    await safe_edit(callback, text, reply_markup=support_menu_kb)
    await safe_answer(callback)

@router.callback_query(F.data == "faq")
async def faq(callback: CallbackQuery):
    text = (
        "❓ **Частые вопросы**\n"
        "Выберите тему:\n"
        "• 📦 Как купить?\n"
        "• 🛡 Гарантия\n"
        "• 💰 Пополнение\n"
        "• ⚠️ Аккаунт не работает"
    )
    await safe_edit(callback, text, reply_markup=faq_kb)
    await safe_answer(callback)

@router.callback_query(F.data == "faq_how_to_buy")
async def faq_how_to_buy(callback: CallbackQuery):
    text = (
        "📦 **Как купить аккаунт?**\n\n"
        "1️⃣ Выберите страну\n"
        "2️⃣ Выберите тип (саморег/авторег)\n"
        "3️⃣ Нажмите 'Купить'\n"
        "4️⃣ Подтвердите покупку\n"
        "5️⃣ Получите данные аккаунта!"
    )
    await safe_edit(callback, text, reply_markup=back_to_support_kb)
    await safe_answer(callback)

@router.callback_query(F.data == "faq_guarantee")
async def faq_guarantee(callback: CallbackQuery):
    text = (
        "🛡 **Гарантия**\n\n"
        "• Стандарт: 24 часа\n"
        "• Со страховкой (+20%): пожизненная\n\n"
        "Если аккаунт не работает — создайте тикет!"
    )
    await safe_edit(callback, text, reply_markup=back_to_support_kb)
    await safe_answer(callback)

@router.callback_query(F.data == "faq_payment")
async def faq_payment(callback: CallbackQuery):
    text = (
        "💰 **Пополнение баланса**\n\n"
        "• СБП — быстро и без комиссии\n"
        "• QR СБП — сканируйте и оплатите\n"
        "• Telegram Stars — удобно\n"
        "• Через админа — от 500₽"
    )
    await safe_edit(callback, text, reply_markup=back_to_support_kb)
    await safe_answer(callback)

@router.callback_query(F.data == "faq_broken")
async def faq_broken(callback: CallbackQuery):
    text = (
        "⚠️ **Аккаунт не работает?**\n\n"
        "1. Проверьте данные ещё раз\n"
        "2. Попробуйте сбросить сессии\n"
        "3. Создайте тикет — мы поможем!"
    )
    await safe_edit(callback, text, reply_markup=back_to_support_kb)
    await safe_answer(callback)

@router.callback_query(F.data == "faq_referral")
async def faq_referral(callback: CallbackQuery):
    text = (
        "🎁 **Реферальная программа**\n\n"
        "Приглашайте друзей и получайте 10% с их покупок!"
    )
    await safe_edit(callback, text, reply_markup=back_to_support_kb)
    await safe_answer(callback)

@router.callback_query(F.data == "create_ticket")
async def create_ticket_handler(callback: CallbackQuery, state: FSMContext):
    text = "🎫 **Создать тикет**\nВыберите тип обращения:"
    await safe_edit(callback, text, reply_markup=ticket_type_kb)
    await safe_answer(callback)

@router.callback_query(F.data.startswith("ticket_type:"))
async def ticket_type_selected(callback: CallbackQuery, state: FSMContext):
    ticket_type = callback.data.split(":")[1]
    await state.update_data(ticket_type=ticket_type)
    await state.set_state(TicketState.waiting_message)
    text = "✏️ **Опишите вашу проблему:**\n(макс. 3000 символов)"
    await callback.message.answer(text)
    await safe_answer(callback)

@router.message(TicketState.waiting_message, F.text)
async def ticket_message_received(message: Message, state: FSMContext):
    text = message.text.strip()
    if len(text) > TICKET_MAX_LEN:
        await message.answer(f"❌ Слишком длинное сообщение. Максимум {TICKET_MAX_LEN} символов.")
        return
    if len(text) < 5:
        await message.answer("❌ Опишите проблему подробнее (минимум 5 символов).")
        return
    data = await state.get_data()
    ticket_type = data.get("ticket_type", "other")
    user = message.from_user
    ticket_id = create_ticket(
        user_id=user.id,
        username=user.username or "",
        full_name=user.full_name or "",
        ticket_type=ticket_type,
        message=text
    )
    await state.clear()
    await message.answer(
        f"✅ **Тикет #{ticket_id} создан!**\n"
        f"Тип: {ticket_type}\n"
        f"Мы ответим вам в ближайшее время.",
        reply_markup=back_to_support_kb
    )

@router.callback_query(F.data == "my_tickets")
async def my_tickets(callback: CallbackQuery):
    tickets = get_user_tickets(callback.from_user.id)
    if not tickets:
        text = "📋 **Мои тикеты**\nУ вас пока нет обращений."
        await safe_edit(callback, text, reply_markup=back_to_support_kb)
        await safe_answer(callback)
        return
    text = "📋 **Мои тикеты:**\n"
    for t in tickets:
        status = "✅ Закрыт" if t["status"] == "closed" else "🟢 Открыт"
        text += f"#{t['id']} — {t['type']} — {status}\n"
    await safe_edit(callback, text, reply_markup=back_to_support_kb)
    await safe_answer(callback)

@router.callback_query(F.data.startswith("ticket_from_purchase:"))
async def ticket_from_purchase(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) < 2:
        await safe_answer(callback, "❌ Неверные данные", show_alert=True)
        return
    try:
        purchase_id = int(parts[1])
    except (ValueError, TypeError):
        await safe_answer(callback, "❌ Неверный ID покупки", show_alert=True)
        return
    user_id = callback.from_user.id
    # FIX 16: проверяем что purchase принадлежит пользователю
    purchases = get_user_purchases(user_id)
    found = any(p["id"] == purchase_id for p in purchases)
    if not found:
        await safe_answer(callback, "❌ Покупка не найдена или не принадлежит вам", show_alert=True)
        return
    ticket_id = create_ticket(
        user_id=user_id,
        username=callback.from_user.username or "",
        full_name=callback.from_user.full_name or "",
        ticket_type="purchase",
        message=f"Вопрос по покупке #{purchase_id}",
        purchase_id=purchase_id
    )
    await safe_answer(callback, f"✅ Тикет #{ticket_id} создан по покупке #{purchase_id}", show_alert=True)
