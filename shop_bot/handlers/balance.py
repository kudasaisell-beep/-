from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from tg_utils import safe_edit, safe_answer
from database import add_balance, get_user, create_deposit, get_deposit
from keyboards import balance_kb, stars_amount_kb, back_to_balance_kb, back_to_main_kb
from config import ADMIN_CHAT_ID
import logging

router = Router()

class StarsState(StatesGroup):
    waiting_amount = State()

class CardDepositState(StatesGroup):
    waiting_amount = State()
    waiting_receipt = State()

CARD_NUMBER = "2200 7020 7997 0948"

@router.callback_query(F.data == "top_up")
async def top_up(callback: CallbackQuery):
    text = (
        "💰 <b>Пополнение баланса</b>\n\n"
        "Выберите способ пополнения:"
    )
    await safe_edit(callback, text, reply_markup=balance_kb)
    await safe_answer(callback)


# ========== ПОПОЛНЕНИЕ ЧЕРЕЗ КАРТУ ==========

@router.callback_query(F.data == "pay_card")
async def pay_card(callback: CallbackQuery, state: FSMContext):
    text = (
        "💳 <b>Пополнение через перевод на карту</b>\n\n"
        "Введите сумму пополнения (минимум 100₽):"
    )
    await state.set_state(CardDepositState.waiting_amount)
    await state.update_data(user_id=callback.from_user.id, username=callback.from_user.username, full_name=callback.from_user.full_name)
    await callback.message.answer(text)
    await safe_answer(callback)


@router.message(CardDepositState.waiting_amount, F.text)
async def process_card_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
        if amount < 100:
            await message.answer("❌ Минимальная сумма пополнения — 100₽")
            return
    except ValueError:
        await message.answer("❌ Введите целое число (сумму в ₽)")
        return

    await state.update_data(amount=amount)
    await state.set_state(CardDepositState.waiting_receipt)

    text = (
        f"💳 <b>Пополнение на {amount}₽</b>\n\n"
        f"Переведите <b>{amount}₽</b> на карту:\n"
        f"<code>{CARD_NUMBER}</code>\n\n"
        f"После перевода отправьте сюда <b>скриншот чека</b> (фото).\n"
        f"Админ проверит и зачислит средства вручную."
    )
    await message.answer(text, reply_markup=back_to_main_kb)


@router.message(CardDepositState.waiting_receipt, F.photo)
async def process_card_receipt(message: Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount", 0)
    user_id = data.get("user_id", message.from_user.id)
    username = data.get("username", message.from_user.username)
    full_name = data.get("full_name", message.from_user.full_name)

    if not amount:
        await message.answer("❌ Ошибка: сумма не найдена. Начните заново.", reply_markup=back_to_main_kb)
        await state.clear()
        return

    # Сохраняем заявку в БД
    deposit_id = create_deposit(user_id, amount, "pending")

    # Пересылаем админу
    if ADMIN_CHAT_ID:
        from keyboards import admin_deposit_kb
        photo = message.photo[-1]  # самое большое фото
        caption = (
            f"💳 <b>Новая заявка на пополнение</b>\n\n"
            f"👤 Пользователь: <code>{user_id}</code>\n"
            f"Имя: {full_name or '—'}\n"
            f"Username: @{username or '—'}\n"
            f"💰 Сумма: <b>{amount}₽</b>\n"
            f"🆔 Заявка: <code>{deposit_id}</code>\n\n"
            f"Отправлен чек ниже ⬇️"
        )
        try:
            await message.bot.send_photo(
                chat_id=ADMIN_CHAT_ID,
                photo=photo.file_id,
                caption=caption,
                reply_markup=admin_deposit_kb(deposit_id, user_id, amount)
            )
        except Exception as e:
            logging.error(f"Failed to forward deposit to admin: {e}")
            await message.answer("⚠️ Ошибка отправки админу. Попробуйте позже.", reply_markup=back_to_main_kb)
            await state.clear()
            return

    await state.clear()
    await message.answer(
        f"✅ <b>Заявка на пополнение {amount}₽ отправлена!</b>\n"
        f"Админ проверит чек и зачислит средства. Обычно это занимает до 15 минут.",
        reply_markup=back_to_main_kb
    )


@router.message(CardDepositState.waiting_receipt)
async def process_card_receipt_invalid(message: Message, state: FSMContext):
    await message.answer("❌ Пожалуйста, отправьте <b>фото чека</b> (скриншот перевода).")


# ========== СТАРЫЕ СПОСОБЫ ==========

@router.callback_query(F.data == "pay_qr")
async def pay_qr(callback: CallbackQuery):
    text = (
        "📱 <b>QR СБП</b>\n\n"
        "Отсканируйте QR-код и оплатите.\n"
        "После оплаты отправьте скриншот админу @usen1me"
    )
    await safe_edit(callback, text, reply_markup=back_to_balance_kb)
    await safe_answer(callback)


@router.callback_query(F.data == "pay_stars_menu")
async def pay_stars_menu(callback: CallbackQuery):
    text = "⭐ <b>Telegram Stars</b>\n\nВыберите сумму:"
    await safe_edit(callback, text, reply_markup=stars_amount_kb)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("pay_stars:"))
async def pay_stars(callback: CallbackQuery):
    amount = int(callback.data.split(":")[1])
    text = (
        f"⭐ <b>Пополнение через Stars</b>\n\n"
        f"Отправьте {amount} Stars боту.\n"
        f"Баланс будет пополнен на {int(amount * 1.3)}₽"
    )
    await safe_edit(callback, text, reply_markup=back_to_balance_kb)
    await safe_answer(callback)


@router.callback_query(F.data == "pay_stars_custom")
async def pay_stars_custom(callback: CallbackQuery, state: FSMContext):
    await state.set_state(StarsState.waiting_amount)
    text = "💰 Введите количество Stars (минимум 50):"
    await callback.message.answer(text)
    await safe_answer(callback)


@router.message(StarsState.waiting_amount, F.text)
async def process_stars_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
        if amount < 50:
            await message.answer("❌ Минимум 50 Stars")
            return
        await state.clear()
        await message.answer(
            f"⭐ Отправьте {amount} Stars боту.\n"
            f"Баланс будет пополнен на {int(amount * 1.3)}₽",
            reply_markup=back_to_main_kb
        )
    except ValueError:
        await message.answer("❌ Введите число")
