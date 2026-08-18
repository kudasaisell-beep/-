from aiogram import Router, F
from aiogram.types import CallbackQuery
from tg_utils import safe_edit, safe_answer
from database import get_user
from keyboards import back_to_main_kb

router = Router()

@router.callback_query(F.data == "referral")
async def referral(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    bot_username = (await callback.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start=ref{callback.from_user.id}"
    text = (
        f"🎁 <b>Реферальная программа</b>

"
        f"Ваша ссылка:
<code>{link}</code>

"
        f"Приглашено: <b>{user['referrals']}</b>
"
        f"Заработано: <b>{int(user['ref_earnings'])}₽</b>

"
        f"Вы получаете <b>10%</b> с каждой покупки реферала!"
    )
    await safe_edit(callback, text, reply_markup=back_to_main_kb)
    await safe_answer(callback)
