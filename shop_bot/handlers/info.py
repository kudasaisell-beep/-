from aiogram import Router, F
from tg_utils import safe_answer, safe_edit
from aiogram.types import CallbackQuery

from keyboards import faq_kb, back_to_main_kb

router = Router()


@router.callback_query(F.data == "info")
async def info_handler(callback: CallbackQuery):
    text = (
        f"ℹ️ <b>Информация о магазине</b>\n\n"
        f"🛒 <b>TG Shop</b> — надёжный магазин Telegram-аккаунтов с автовыдачей.\n\n"
        f"📦 <b>Типы аккаунтов:</b>\n"
        f"• 🧑 <b>Саморег (физ)</b> — регистрация на физические SIM-карты, живые номера\n"
        f"• 🤖 <b>Авторег (вирт)</b> — виртуальные номера, автоматическая регистрация\n\n"
        f"🛡 <b>Гарантия 24 часа</b> — если аккаунт не работает, вернём деньги или заменим.\n"
        f"🛡 <b>Пожизненная гарантия</b> (+20%) — застрахуй аккаунт навсегда!\n"
        f"⚡ <b>Моментальная выдача</b> — после оплаты данные приходят мгновенно.\n"
        f"🔒 <b>Только проверенные</b> — все аккаунты проходят верификацию, без спамблока.\n\n"
        f"👇 Выбери тему ниже:"
    )
    await safe_edit(callback, text, reply_markup=faq_kb)
    await safe_answer(callback, )
