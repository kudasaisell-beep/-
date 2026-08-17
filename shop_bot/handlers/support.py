from aiogram import Router, F
from tg_utils import safe_answer, safe_edit
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import (
    create_ticket, get_user_tickets, get_ticket, update_ticket_status,
    get_user_purchases, add_log
)
from keyboards import (
    support_menu_kb, faq_kb, back_to_main_kb, back_to_support_kb,
    ticket_type_kb, admin_ticket_kb
)
from config import ADMIN_CHAT_ID, TOPIC_MONITORING

router = Router()


class TicketState(StatesGroup):
    waiting_type = State()
    waiting_message = State()
    waiting_reply = State()


@router.callback_query(F.data == "support_menu")
async def support_menu(callback: CallbackQuery):
    text = (
        f"📞 <b>Центр поддержки</b>\n"
        f"Выберите нужный раздел:\n"
        f"• ❓ FAQ — ответы на частые вопросы\n"
        f"• 📦 Как купить? — подробная инструкция\n"
        f"• 🎫 Создать тикет — написать в поддержку\n"
        f"• 📋 Мои тикеты — история обращений"
    )
    await safe_edit(callback, text, reply_markup=support_menu_kb)
    await safe_answer(callback, )


@router.callback_query(F.data == "faq")
async def faq_menu(callback: CallbackQuery):
    text = (
        f"❓ <b>Частые вопросы</b>\n"
        f"Выбери интересующую тему ниже 👇"
    )
    await safe_edit(callback, text, reply_markup=faq_kb)
    await safe_answer(callback, )


@router.callback_query(F.data == "faq_how_to_buy")
async def faq_how_to_buy(callback: CallbackQuery):
    text = (
        f"📦 <b>Как купить аккаунт?</b>\n\n"
        f"1️⃣ Нажми <b>📋 Покупка аккаунта</b> в главном меню\n"
        f"2️⃣ Выбери страну из списка или найди через поиск\n"
        f"3️⃣ Выбери тип: <b>🧑 Саморег</b> (физ) или <b>🤖 Авторег</b> (вирт)\n"
        f"4️⃣ Укажи количество (скидка 3% за 2 шт, 5% за 3, 7% за 4+)\n"
        f"5️⃣ Нажми <b>☑️ Купить</b> — если баланса недостаточно, пополни через <b>⭐ Stars</b>\n"
        f"6️⃣ Получи данные мгновенно! Сохрани их — повторно не покажем.\n\n"
        f"💡 <b>Совет:</b> После покупки ты можешь создать тикет прямо из архива покупок, если что-то не так."
    )
    await safe_edit(callback, text, reply_markup=faq_kb)
    await safe_answer(callback, )


@router.callback_query(F.data == "faq_guarantee")
async def faq_guarantee(callback: CallbackQuery):
    text = (
        f"🛡 <b>Гарантия и возврат</b>\n\n"
        f"• <b>24 часа</b> на проверку аккаунта с момента покупки\n"
        f"• Если аккаунт не работает (бан, спамблок, неверные данные) — создай тикет\n"
        f"• Мы проверим и вернём деньги или заменим аккаунт\n"
        f"• Возврат осуществляется на баланс бота в течение 24 часов\n\n"
        f"🛡 <b>Пожизненная гарантия</b> (+20% к цене):\n"
        f"• Возврат или замена аккаунта навсегда\n"
        f"• Приоритет в поддержке\n\n"
        f"⚠️ Гарантия не распространяется на аккаунты, которые вышли из строя по твоей вине (слишком быстрая рассылка и т.д.)"
    )
    await safe_edit(callback, text, reply_markup=faq_kb)
    await safe_answer(callback, )


@router.callback_query(F.data == "faq_payment")
async def faq_payment(callback: CallbackQuery):
    text = (
        f"💰 <b>Способы пополнения</b>\n\n"
        f"• <b>⭐ Telegram Stars</b> — мгновенно, автоматически, курс 1 Star = 1.3 ₽\n"
        f"• <b>💳 СБП / QR</b> — в разработке, пиши админу\n"
        f"• <b>👤 Через администратора</b> — от 500 ₽, напиши @usen1me\n\n"
        f"⚡ Пополнение через Stars происходит автоматически — баланс зачисляется сразу после оплаты."
    )
    await safe_edit(callback, text, reply_markup=faq_kb)
    await safe_answer(callback, )


@router.callback_query(F.data == "faq_broken")
async def faq_broken(callback: CallbackQuery):
    text = (
        f"⚠️ <b>Аккаунт не работает?</b>\n\n"
        f"1. Убедись, что вводишь данные правильно (телефон, пароль, сессия)\n"
        f"2. Проверь, не включён ли 2FA — если да, запроси код через кнопку в архиве покупок\n"
        f"3. Если аккаунт забанен или в спамблоке — создай тикет в течение <b>24 часов</b>\n"
        f"4. Прикрепи скриншот ошибки — это ускорит решение\n\n"
        f"🎫 <b>Создать тикет:</b> 📞 Поддержка → 🎫 Создать тикет"
    )
    await safe_edit(callback, text, reply_markup=faq_kb)
    await safe_answer(callback, )


@router.callback_query(F.data == "faq_referral")
async def faq_referral(callback: CallbackQuery):
    text = (
        f"🎁 <b>Реферальная программа</b>\n\n"
        f"Приглашай друзей и получай <b>10%</b> с каждого их пополнения баланса!\n\n"
        f"Как это работает:\n"
        f"1. Скопируй свою реферальную ссылку в личном кабинете\n"
        f"2. Отправь другу — он перейдёт и запустит бота\n"
        f"3. Когда друг пополнит баланс — тебе автоматически придёт 10%\n"
        f"4. Выводи заработанное или трать на покупки\n\n"
        f"💰 Нет лимитов — чем больше друзей, тем больше доход!"
    )
    await safe_edit(callback, text, reply_markup=faq_kb)
    await safe_answer(callback, )


# CREATE TICKET
@router.callback_query(F.data == "create_ticket")
async def create_ticket_start(callback: CallbackQuery, state: FSMContext):
    text = (
        f"🎫 <b>Создание тикета</b>\n"
        f"Выберите тему обращения:"
    )
    await safe_edit(callback, text, reply_markup=ticket_type_kb)
    await state.set_state(TicketState.waiting_type)
    await safe_answer(callback, )


@router.callback_query(F.data.startswith("ticket_type:"), TicketState.waiting_type)
async def ticket_type_selected(callback: CallbackQuery, state: FSMContext):
    ticket_type = callback.data.split(":")[1]
    await state.update_data(ticket_type=ticket_type)

    type_names = {
        "purchase": "🛍 Вопрос по покупке",
        "payment": "💰 Вопрос по пополнению",
        "tech": "🔧 Техническая проблема",
        "other": "❓ Другой вопрос",
    }

    text = (
        f"🎫 <b>Создание тикета</b>\n"
        f"Тема: {type_names.get(ticket_type, ticket_type)}\n"
        f"Опишите вашу проблему подробно.\n"
        f"Если это вопрос по конкретной покупке — укажите страну и тип аккаунта."
    )
    await safe_edit(callback, text, reply_markup=back_to_support_kb)
    await state.set_state(TicketState.waiting_message)
    await safe_answer(callback, )


@router.message(TicketState.waiting_message, F.text)
async def ticket_message_sent(message: Message, state: FSMContext):
    data = await state.get_data()
    ticket_type = data.get("ticket_type", "other")
    ticket_message = message.text.strip()

    if len(ticket_message) < 5:
        await message.answer(
            "❌ Сообщение слишком короткое. Опишите проблему подробнее.",
            reply_markup=back_to_support_kb
        )
        return

    ticket_id = create_ticket(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        ticket_type=ticket_type,
        message=ticket_message
    )

    add_log(message.from_user.id, "ticket_created", f"ticket_id={ticket_id}")

    type_names = {
        "purchase": "🛍 Покупка",
        "payment": "💰 Пополнение",
        "tech": "🔧 Техника",
        "other": "❓ Другое",
    }

    admin_text = (
        f"🎫 <b>Новый тикет #{ticket_id}</b>\n"
        f"👤 Пользователь: <code>{message.from_user.id}</code>\n"
        f"👤 @{message.from_user.username or '—'} | {message.from_user.full_name}\n"
        f"📌 Тема: {type_names.get(ticket_type, ticket_type)}\n\n"
        f"💬 Сообщение:\n"
        f"<blockquote>{ticket_message[:800]}</blockquote>"
    )

    if ADMIN_CHAT_ID:
        try:
            kwargs = {}
            if TOPIC_MONITORING:
                kwargs["message_thread_id"] = TOPIC_MONITORING
            await message.bot.send_message(
                ADMIN_CHAT_ID,
                admin_text,
                reply_markup=admin_ticket_kb(ticket_id),
                parse_mode="HTML",
                **kwargs
            )
        except Exception as e:
            print(f"Failed to send ticket to admin chat: {e}")

    await message.answer(
        f"✅ <b>Тикет #{ticket_id} создан!</b>\n"
        f"Мы получили ваше обращение и ответим в ближайшее время.\n"
        f"Отслеживать статус можно в разделе 📋 Мои тикеты.",
        reply_markup=back_to_support_kb
    )
    await state.clear()


# MY TICKETS
@router.callback_query(F.data == "my_tickets")
async def my_tickets(callback: CallbackQuery):
    tickets = get_user_tickets(callback.from_user.id)
    if not tickets:
        text = (
            f"📋 <b>Мои тикеты</b>\n\n"
            f"У вас пока нет обращений.\n"
            f"Создать тикет: 📞 Поддержка → 🎫 Создать тикет"
        )
        await safe_edit(callback, text, reply_markup=back_to_support_kb)
        await safe_answer(callback, )
        return

    text = "📋 <b>Мои тикеты:</b>\n"
    status_emoji = {"open": "🟢", "waiting": "🟡", "closed": "🔴"}

    buttons = []
    for t in tickets[:10]:
        status = t.get("status", "open")
        emoji = status_emoji.get(status, "⚪")
        text += f"{emoji} <b>#{t['id']}</b> — {t['created_at'].strftime('%d.%m %H:%M')}\n"
        buttons.append([
            InlineKeyboardButton(
                text=f"{emoji} Тикет #{t['id']}",
                callback_data=f"view_ticket:{t['id']}"
            )
        ])

    buttons.append([InlineKeyboardButton(text="◀️ Назад в поддержку", callback_data="support_menu")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await safe_edit(callback, text, reply_markup=kb)
    await safe_answer(callback, )


@router.callback_query(F.data.startswith("view_ticket:"))
async def view_ticket(callback: CallbackQuery):
    ticket_id = int(callback.data.split(":")[1])
    ticket = get_ticket(ticket_id)

    if not ticket or ticket["user_id"] != callback.from_user.id:
        await safe_answer(callback, "❌ Тикет не найден", show_alert=True)
        return

    type_names = {
        "purchase": "🛍 Покупка",
        "payment": "💰 Пополнение",
        "tech": "🔧 Техника",
        "other": "❓ Другое",
    }
    status_names = {"open": "🟢 Открыт", "waiting": "🟡 В ожидании", "closed": "🔴 Закрыт"}

    text = (
        f"🎫 <b>Тикет #{ticket['id']}</b>\n"
        f"📌 Тема: {type_names.get(ticket['type'], ticket['type'])}\n"
        f"📊 Статус: {status_names.get(ticket['status'], ticket['status'])}\n"
        f"🕐 Создан: {ticket['created_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
        f"💬 <b>Ваше сообщение:</b>\n"
        f"<blockquote>{ticket['message'][:600]}</blockquote>"
    )

    if ticket.get("admin_reply"):
        text += f"\n\n👨‍💼 <b>Ответ поддержки:</b>\n<blockquote>{ticket['admin_reply'][:600]}</blockquote>"

    buttons = [[InlineKeyboardButton(text="◀️ Назад к тикетам", callback_data="my_tickets")]]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await safe_edit(callback, text, reply_markup=kb)
    await safe_answer(callback, )


# TICKET FROM PURCHASE
@router.callback_query(F.data.startswith("ticket_from_purchase:"))
async def ticket_from_purchase(callback: CallbackQuery, state: FSMContext):
    purchase_id = int(callback.data.split(":")[1])
    purchases = get_user_purchases(callback.from_user.id)
    purchase = next((p for p in purchases if p["id"] == purchase_id), None)

    if not purchase:
        await safe_answer(callback, "❌ Покупка не найдена", show_alert=True)
        return

    await state.update_data(
        ticket_type="purchase",
        purchase_id=purchase_id,
        purchase_info=f"{purchase['country_name']} — {'саморег' if purchase['account_type'] == 'samoreg' else 'авторег'}"
    )

    text = (
        f"🎫 <b>Тикет по покупке #{purchase_id}</b>\n"
        f"🌍 Аккаунт: {purchase['country_name']}\n"
        f"📱 Тип: {'саморег' if purchase['account_type'] == 'samoreg' else 'авторег'}\n"
        f"📅 Дата: {purchase['created_at']}\n\n"
        f"Опишите вашу проблему с этим аккаунтом:"
    )
    await safe_edit(callback, text, reply_markup=back_to_support_kb)
    await state.set_state(TicketState.waiting_message)
    await safe_answer(callback, )


# MAIN MENU
@router.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery):
    from keyboards import main_menu_kb
    text = (
        f"👋 Привет, <b>{callback.from_user.full_name}</b>!\n"
        f"Добро пожаловать в магазин Telegram-аккаунтов.\n"
        f"Выбирай нужный раздел ниже 👇"
    )
    await safe_edit(callback, text, reply_markup=main_menu_kb)
    await safe_answer(callback, )


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await safe_answer(callback, )
