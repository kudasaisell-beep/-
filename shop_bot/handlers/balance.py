from aiogram import Router, F
from tg_utils import safe_answer, safe_edit
from aiogram.types import CallbackQuery, Message, LabeledPrice, PreCheckoutQuery

from database import get_user, add_balance_tx
from keyboards import balance_kb, profile_kb, back_to_main_kb, stars_amount_kb, back_to_balance_kb
from config import ADMIN_CHAT_ID, TOPIC_TOPUPS

router = Router()


async def notify_admin_topup(bot, text: str):
    if ADMIN_CHAT_ID:
        try:
            kwargs = {}
            if TOPIC_TOPUPS:
                kwargs["message_thread_id"] = TOPIC_TOPUPS
            await bot.send_message(ADMIN_CHAT_ID, text, parse_mode="HTML", **kwargs)
        except Exception:
            pass


@router.callback_query(F.data == "top_up")
async def top_up(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    balance = user.get("balance", 0) or 0 if user else 0

    text = (
        f"💰 <b>Баланс</b>\n\n"
        f"💵 Текущий баланс: <b>{round(balance, 2)} ₽</b>\n\n"
        f"Выберите способ пополнения:"
    )
    await safe_edit(callback, text, reply_markup=balance_kb)
    await safe_answer(callback, )


@router.callback_query(F.data == "pay_sbp")
async def pay_sbp(callback: CallbackQuery):
    text = (
        f"💳 <b>СБП</b>\n\n"
        f"🛠 Оплата через СБП в разработке.\n\n"
        f"Попробуйте оплату через Stars или обратитесь к администратору."
    )
    await safe_edit(callback, text, reply_markup=back_to_balance_kb)
    await safe_answer(callback, )


@router.callback_query(F.data == "pay_qr")
async def pay_qr(callback: CallbackQuery):
    text = (
        f"📱 <b>QR СБП</b>\n\n"
        f"🛠 Оплата через QR СБП в разработке.\n\n"
        f"Попробуйте оплату через Stars или обратитесь к администратору."
    )
    await safe_edit(callback, text, reply_markup=back_to_balance_kb)
    await safe_answer(callback, )


@router.callback_query(F.data == "pay_stars_menu")
async def pay_stars_menu(callback: CallbackQuery):
    text = (
        f"⭐ <b>Пополнение через Telegram Stars</b>\n\n"
        f"Курс: <b>1 Star = 1.3 ₽</b>\n\n"
        f"Выберите сумму пополнения:"
    )
    await safe_edit(callback, text, reply_markup=stars_amount_kb)
    await safe_answer(callback, )


@router.callback_query(F.data.startswith("pay_stars:"))
async def pay_stars_invoice(callback: CallbackQuery):
    stars = int(callback.data.split(":")[1])
    rubles = round(stars * 1.3, 2)

    await callback.bot.send_invoice(
        chat_id=callback.message.chat.id,
        title="Пополнение баланса",
        description=f"Пополнение баланса на {stars} Stars ({rubles} ₽)",
        payload=f"topup_stars_{stars}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Stars", amount=stars)],
        start_parameter="topup",
    )
    await safe_answer(callback, )


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout: PreCheckoutQuery):
    await pre_checkout.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    payment = message.successful_payment
    stars = payment.total_amount
    rubles = round(stars * 1.3, 2)

    result = add_balance_tx(message.from_user.id, rubles)
    if not result['ok']:
        await message.answer('❌ Ошибка зачисления. Обратитесь в поддержку.')
        return

    # Реферальный бонус 10%
    user = get_user(message.from_user.id)
    if user and user.get("referred_by"):
        ref_bonus = round(rubles * 0.1, 2)
        from database import add_balance, get_db
        add_balance(user["referred_by"], ref_bonus)
        conn = get_db()
        c = conn.cursor()
        c.execute(
            "UPDATE users SET ref_earnings = ref_earnings + ? WHERE user_id = ?",
            (ref_bonus, user["referred_by"])
        )
        conn.commit()
        conn.close()
        try:
            await message.bot.send_message(
                user["referred_by"],
                f"🎉 <b>Реферальный бонус!</b>\n\n"
                f"Ваш реферал пополнил баланс на {rubles} ₽.\n"
                f"Вам начислено: <b>{ref_bonus} ₽</b> (10%)",
                parse_mode="HTML"
            )
        except Exception:
            pass

    username = user.get("username", "—") if user else "—"
    admin_text = (
        f"💰 <b>Пополнение баланса!</b>\n\n"
        f"👤 Пользователь: <code>{message.from_user.id}</code>\n"
        f"👤 Username: @{username}\n"
        f"⭐ Списано Stars: {stars}\n"
        f"💵 Зачислено: {rubles} ₽"
    )
    await notify_admin_topup(message.bot, admin_text)

    await message.answer(
        f"✅ <b>Баланс пополнен!</b>\n\n"
        f"Списано Stars: {stars}\n"
        f"Зачислено: {rubles} ₽\n\n"
        f"Спасибо за пополнение!",
        reply_markup=back_to_main_kb
    )
