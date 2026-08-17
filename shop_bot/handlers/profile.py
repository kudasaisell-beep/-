from aiogram import Router, F
from tg_utils import safe_answer, safe_edit
from aiogram.types import CallbackQuery

from database import get_user, get_user_purchases
from keyboards import profile_kb, back_to_main_kb, back_to_profile_kb

router = Router()

country_map_local = {
    "US": ("США", "🇺🇸"), "KZ": ("Казахстан", "🇰🇿"), "IN": ("Индия", "🇮🇳"),
    "ID": ("Индонезия", "🇮🇩"), "PH": ("Филиппины", "🇵🇭"), "VN": ("Вьетнам", "🇻🇳"),
    "BR": ("Бразилия", "🇧🇷"), "AR": ("Аргентина", "🇦🇷"), "TR": ("Турция", "🇹🇷"),
    "RO": ("Румыния", "🇷🇴"), "PL": ("Польша", "🇵🇱"), "DE": ("Германия", "🇩🇪"),
    "GB": ("Великобритания", "🇬🇧"), "IT": ("Италия", "🇮🇹"), "ES": ("Испания", "🇪🇸"),
    "FR": ("Франция", "🇫🇷"), "NL": ("Нидерланды", "🇳🇱"), "CZ": ("Чехия", "🇨🇿"),
    "BG": ("Болгария", "🇧🇬"), "MX": ("Мексика", "🇲🇽"), "CL": ("Чили", "🇨🇱"),
    "PE": ("Перу", "🇵🇪"), "CO": ("Колумбия", "🇨🇴"), "TH": ("Таиланд", "🇹🇭"),
    "MY": ("Малайзия", "🇲🇾"), "PK": ("Пакистан", "🇵🇰"), "BD": ("Бангладеш", "🇧🇩"),
    "EG": ("Египет", "🇪🇬"), "MA": ("Марокко", "🇲🇦"), "NG": ("Нигерия", "🇳🇬"),
    "KE": ("Кения", "🇰🇪"), "ZA": ("ЮАР", "🇿🇦"),
}


@router.callback_query(F.data == "profile")
async def profile_handler(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        await safe_answer(callback, "❌ Пользователь не найден", show_alert=True)
        return

    balance = user.get("balance", 0) or 0
    total_spent = user.get("total_spent", 0) or 0
    spent_today = user.get("spent_today", 0) or 0
    purchases = get_user_purchases(callback.from_user.id)
    accounts_bought = len(purchases)

    bot_username = (await callback.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref{callback.from_user.id}"

    text = (
        f"👤 <b>Личный кабинет</b>\n\n"
        f"💵 Баланс: <b>{round(balance, 2)} ₽</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• 📱 Куплено аккаунтов: <b>{accounts_bought}</b>\n"
        f"• 💸 Потрачено сегодня: <b>{round(spent_today, 2)} ₽</b>\n"
        f"• 💸 Всего потрачено: <b>{round(total_spent, 2)} ₽</b>\n\n"
        f"🆔 ID: <code>{user['user_id']}</code>\n"
        f"👤 Username: @{user.get('username', '—')}\n\n"
        f"🎁 <b>Приглашай друзей и получай 10% с их пополнений!</b>\n"
        f"🔗 Реферальная ссылка:\n"
        f"<code>{ref_link}</code>"
    )
    await safe_edit(callback, text, reply_markup=profile_kb)
    await safe_answer(callback, )


@router.callback_query(F.data == "my_purchases")
async def my_purchases(callback: CallbackQuery):
    purchases = get_user_purchases(callback.from_user.id)
    if not purchases:
        text = "🛍 <b>Мои покупки</b>\n\nУ вас пока нет покупок."
        await safe_edit(callback, text, reply_markup=back_to_profile_kb)
        await safe_answer(callback, )
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    text = "🛍 <b>Мои покупки:</b>\n\n"

    for idx, p in enumerate(purchases[:10], 1):
        type_label = "саморег" if p["account_type"] == "samoreg" else "авторег"
        text += (
            f"{idx}. {p['country_name']} — {type_label} — "
            f"{int(p['price'])}₽ ({p['created_at']})\n"
        )
        country_code = p.get("country_code", "")
        if country_code:
            buttons.append([
                InlineKeyboardButton(
                    text=f"🔄 Повторить · {p['country_name']} ({type_label})",
                    callback_data=f"repeat_purchase:{country_code}:{p['account_type']}"
                )
            ])

    if len(purchases) > 10:
        text += f"\n...и ещё {len(purchases) - 10} покупок"

    buttons.append([InlineKeyboardButton(text="◀️ Назад в личный кабинет", callback_data="profile")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await safe_edit(callback, text, reply_markup=kb)
    await safe_answer(callback, )


@router.callback_query(F.data.startswith("repeat_purchase:"))
async def repeat_purchase(callback: CallbackQuery):
    parts = callback.data.split(":")
    country_code = parts[1]
    account_type = parts[2]

    name = country_map_local.get(country_code, (country_code, ""))[0]
    flag = country_map_local.get(country_code, ("", "🏳️"))[1]

    from keyboards import country_type_kb
    text = (
        f"{flag} <b>{name}</b>\n"
        f"Выберите тип аккаунта:\n"
        f"• 🧑 <b>Саморег (физ)</b>\n"
        f"• 🤖 <b>Авторег (вирт)</b>"
    )
    await safe_edit(callback, text, reply_markup=country_type_kb(country_code))
    await safe_answer(callback, )


@router.callback_query(F.data == "my_stats")
async def my_stats(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    purchases = get_user_purchases(callback.from_user.id)
    total = sum(p["price"] for p in purchases)

    text = (
        f"📊 <b>Моя статистика</b>\n\n"
        f"📱 Всего покупок: <b>{len(purchases)}</b>\n"
        f"💸 Общая сумма: <b>{round(total, 2)} ₽</b>\n"
        f"💵 Текущий баланс: <b>{round(user.get('balance', 0) or 0, 2)} ₽</b>\n"
        f"🎁 Рефералов: <b>{user.get('referrals', 0) or 0}</b>\n"
        f"💰 Заработано с рефералов: <b>{round(user.get('ref_earnings', 0) or 0, 2)} ₽</b>"
    )
    await safe_edit(callback, text, reply_markup=back_to_profile_kb)
    await safe_answer(callback, )
