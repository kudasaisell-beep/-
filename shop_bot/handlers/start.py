from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from tg_utils import safe_edit
from database import get_or_create_user
from keyboards import main_menu_kb

router = Router()

@router.message(F.text == "/start")
async def cmd_start(message: Message):
    user = get_or_create_user(
        message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name
    )
    text = (
        f"👋 Привет, <b>{message.from_user.full_name}</b>!\n"
        f"Добро пожаловать в мульти-магазин аккаунтов.\n\n"
        f"💰 Баланс: <b>{int(user.get('balance', 0))}₽</b>\n"
        f"🛍 Покупок: <b>{user.get('total_spent', 0)}</b>"
    )
    await message.answer(text, reply_markup=main_menu_kb)

@router.callback_query(F.data == "main_menu")
async def main_menu_cb(callback: CallbackQuery):
    user = get_or_create_user(callback.from_user.id)
    text = (
        f"👋 Привет, <b>{callback.from_user.full_name}</b>!\n"
        f"💰 Баланс: <b>{int(user.get('balance', 0))}₽</b>"
    )
    await safe_edit(callback, text, reply_markup=main_menu_kb)
