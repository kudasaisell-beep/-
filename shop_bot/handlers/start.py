from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from database import get_or_create_user, get_stats, get_user, get_db
from keyboards import main_menu_kb

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    user = get_or_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name
    )

    # Реферальная ссылка: /start ref123456
    args = (message.text or "").split()
    referrer_id = None
    if len(args) > 1 and args[1].startswith("ref"):
        try:
            referrer_id = int(args[1][3:])
        except ValueError:
            pass

    if referrer_id and referrer_id != message.from_user.id:
        referrer = get_user(referrer_id)
        if referrer and not user.get("referred_by"):
            conn = get_db()
            c = conn.cursor()
            # FIX: sqlite3 использует ?, а не %s
            c.execute(
                "UPDATE users SET referred_by = ? WHERE user_id = ?",
                (referrer_id, message.from_user.id)
            )
            c.execute(
                "UPDATE users SET referrals = referrals + 1 WHERE user_id = ?",
                (referrer_id,)
            )
            conn.commit()
            conn.close()

            try:
                await message.bot.send_message(
                    referrer_id,
                    f"🎉 <b>Новый реферал!</b>\n\n"
                    f"Пользователь {message.from_user.full_name} перешёл по твоей ссылке.\n"
                    f"Когда он пополнит баланс — ты получишь 10%!",
                    parse_mode="HTML"
                )
            except Exception:
                pass

    stats = get_stats()

    text = (
        f"👋 <b>Привет, {message.from_user.full_name}!</b>\n"
        f"🛒 Добро пожаловать в <b>TG Shop</b> — магазин качественных Telegram-аккаунтов.\n\n"
        f"📊 <b>О магазине:</b>\n"
        f"• 👥 Покупателей: <b>{stats['total_users']}</b>\n"
        f"• 📦 Аккаунтов продано: <b>{stats['total_purchases']}</b>\n"
        f"• 🌍 Стран: <b>32</b>\n"
        f"• ⚡ Выдача: <b>моментально</b>\n\n"
        f"💡 <b>Как купить?</b>\n"
        f"1. Выбери страну в каталоге\n"
        f"2. Выбери тип (саморег / авторег)\n"
        f"3. Пополни баланс через Stars\n"
        f"4. Получи данные мгновенно!\n\n"
        f"📜 Используя бота, ты принимаешь "
        f"<a href='https://telegra.ph/'>условия соглашения</a> "
        f"(кнопка «📜 Документы» в меню).\n\n"
        f"👇 Выбирай раздел ниже:"
    )
    await message.answer(text, reply_markup=main_menu_kb, disable_web_page_preview=True)
