from aiogram import Router, F
from aiogram.types import CallbackQuery
from tg_utils import safe_edit, safe_answer
from database import get_user
from keyboards import profile_kb, back_to_main_kb

router = Router()

@router.callback_query(F.data == "profile")
async def profile(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        await safe_answer(callback, "❌ Ошибка профиля", show_alert=True)
        return
    text = (
        f"👤 <b>Личный кабинет</b>

"
        f"💰 Баланс: <b>{int(user['balance'])}₽</b>
"
        f"💸 Потрачено всего: <b>{int(user['total_spent'])}₽</b>
"
        f"📅 Сегодня потрачено: <b>{int(user.get('spent_today', 0))}₽</b>
"
        f"🎁 Рефералов: <b>{user['referrals']}</b>
"
        f"💵 Заработано с рефералов: <b>{int(user['ref_earnings'])}₽</b>"
    )
    await safe_edit(callback, text, reply_markup=profile_kb)
    await safe_answer(callback)

@router.callback_query(F.data == "my_stats")
async def my_stats(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        await safe_answer(callback, "❌ Ошибка", show_alert=True)
        return
    text = (
        f"📊 <b>Статистика</b>

"
        f"Покупок: <b>{int(user.get('total_spent', 0))}</b>
"
        f"Рефералов: <b>{user['referrals']}</b>
"
        f"Заработано: <b>{int(user['ref_earnings'])}₽</b>"
    )
    await safe_edit(callback, text, reply_markup=back_to_main_kb)
    await safe_answer(callback)
