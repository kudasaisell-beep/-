from aiogram import Router, F
from aiogram.types import CallbackQuery
from tg_utils import safe_answer, safe_edit

from database import get_user
from keyboards import back_to_profile_kb

router = Router()

# ВНИМАНИЕ: хендлер /start с обработкой реферальных ссылок перенесён в start.py —
# здесь он был мёртвым кодом (aiogram вызывает только первый подошедший
# хендлер, а роутер start подключён раньше, поэтому реф-ссылки не работали).


@router.callback_query(F.data == "referral")
async def referral_info(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    bot_username = (await callback.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref{callback.from_user.id}"
    referrals = user.get("referrals", 0) or 0
    earnings = user.get("ref_earnings", 0) or 0

    text = (
        f"🎁 <b>Реферальная программа</b>\n\n"
        f"Приглашай друзей и получай <b>10%</b> с их пополнений!\n\n"
        f"📊 <b>Твоя статистика:</b>\n"
        f"• 👥 Приглашено: <b>{referrals}</b>\n"
        f"• 💰 Заработано: <b>{round(earnings, 2)} ₽</b>\n\n"
        f"🔗 <b>Твоя ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"Отправь её друзьям — когда они пополнят баланс, ты получишь бонус автоматически!"
    )
    await safe_edit(callback, text, reply_markup=back_to_profile_kb)
    await safe_answer(callback)
