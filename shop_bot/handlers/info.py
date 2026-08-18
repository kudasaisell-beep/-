from aiogram import Router, F
from aiogram.types import CallbackQuery
from tg_utils import safe_edit, safe_answer
from keyboards import back_to_main_kb

router = Router()

@router.callback_query(F.data == "info")
async def info_handler(callback: CallbackQuery):
    text = (
        "ℹ️ <b>Информация</b>

"
        "Мы продаём качественные Telegram-аккаунты.
"
        "• Самореги (физические SIM)
"
        "• Автореги (виртуальные номера)

"
        "Поддержка: @usen1me"
    )
    await safe_edit(callback, text, reply_markup=back_to_main_kb)
    await safe_answer(callback)
