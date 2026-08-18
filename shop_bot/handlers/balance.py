from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from tg_utils import safe_edit, safe_answer
from database import add_balance, get_user
from keyboards import balance_kb, stars_amount_kb, back_to_balance_kb, back_to_main_kb
from config import ADMIN_CHAT_ID
import logging

router = Router()

class StarsState(StatesGroup):
    waiting_amount = State()

@router.callback_query(F.data == "top_up")
async def top_up(callback: CallbackQuery):
    text = (
        "💰 <b>Пополнение баланса</b>

"
        "Выберите способ пополнения:"
    )
    await safe_edit(callback, text, reply_markup=balance_kb)
    await safe_answer(callback)

@router.callback_query(F.data == "pay_sbp")
async def pay_sbp(callback: CallbackQuery):
    text = (
        "💳 <b>СБП</b>

"
        "Переведите на карту:
"
        "<code>2200 0000 0000 0000</code>

"
        "После оплаты отправьте скриншот админу @usen1me"
    )
    await safe_edit(callback, text, reply_markup=back_to_balance_kb)
    await safe_answer(callback)

@router.callback_query(F.data == "pay_qr")
async def pay_qr(callback: CallbackQuery):
    text = (
        "📱 <b>QR СБП</b>

"
        "Отсканируйте QR-код и оплатите.
"
        "После оплаты отправьте скриншот админу @usen1me"
    )
    await safe_edit(callback, text, reply_markup=back_to_balance_kb)
    await safe_answer(callback)

@router.callback_query(F.data == "pay_stars_menu")
async def pay_stars_menu(callback: CallbackQuery):
    text = "⭐ <b>Telegram Stars</b>

Выберите сумму:"
    await safe_edit(callback, text, reply_markup=stars_amount_kb)
    await safe_answer(callback)

@router.callback_query(F.data.startswith("pay_stars:"))
async def pay_stars(callback: CallbackQuery):
    amount = int(callback.data.split(":")[1])
    text = (
        f"⭐ <b>Пополнение через Stars</b>

"
        f"Отправьте {amount} Stars боту.
"
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
            f"⭐ Отправьте {amount} Stars боту.
"
            f"Баланс будет пополнен на {int(amount * 1.3)}₽",
            reply_markup=back_to_main_kb
        )
    except ValueError:
        await message.answer("❌ Введите число")
