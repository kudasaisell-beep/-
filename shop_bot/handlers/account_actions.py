from aiogram import Router, F
from tg_utils import safe_answer, safe_edit
from aiogram.types import CallbackQuery
from datetime import datetime

from database import get_user_purchases, create_code_request, add_log
from lzt_api import reset_sessions_lzt, validate_account_lzt
from keyboards import back_to_main_kb, copy_data_kb

router = Router()


@router.callback_query(F.data.startswith("account_details:"))
async def account_details(callback: CallbackQuery):
    purchase_id = int(callback.data.split(":")[1])
    purchases = get_user_purchases(callback.from_user.id)
    purchase = next((p for p in purchases if p["id"] == purchase_id), None)
    if not purchase:
        await safe_answer(callback, "❌ Покупка не найдена", show_alert=True)
        return

    type_label = "саморег" if purchase["account_type"] == "samoreg" else "авторег"

    # Гарантия
    is_insured = purchase.get("is_insured", False)
    guarantee_until = purchase.get("guarantee_until")
    if is_insured:
        guarantee_text = "🛡 <b>Пожизненная гарантия</b> (застрахован)"
    elif guarantee_until:
        now = datetime.now()
        if guarantee_until > now:
            hours_left = int((guarantee_until - now).total_seconds() // 3600)
            guarantee_text = f"🛡 Гарантия: <b>{hours_left}ч</b> осталось"
        else:
            guarantee_text = "⚠️ Гарантия истекла (24ч прошло)"
    else:
        guarantee_text = "🛡 Гарантия: 24ч"

    # Характеристики
    age = purchase.get("item_age_days")
    age_str = f"{age} дней" if age is not None else "неизвестно"
    avatar = "✅ Есть" if purchase.get("has_avatar") else "❌ Нет"
    reg = purchase.get("reg_date") or "неизвестно"
    contacts = purchase.get("contacts_count")
    contacts_str = f"{contacts}" if contacts is not None else "неизвестно"
    premium = "✅ Есть" if purchase.get("has_premium") else "❌ Нет"

    text = (
        f"📦 <b>Данные аккаунта</b>\n"
        f"🌍 Страна: {purchase['country_name']}\n"
        f"📱 Тип: {type_label}\n"
        f"📅 Дата покупки: {purchase['created_at']}\n"
        f"{guarantee_text}\n\n"
        f"📊 <b>Характеристики:</b>\n"
        f"  ⏱ Возраст: {age_str}\n"
        f"  🖼 Аватарка: {avatar}\n"
        f"  📅 Регистрация: {reg}\n"
        f"  👥 Контакты: {contacts_str}\n"
        f"  ⭐ Премиум: {premium}\n\n"
        f"<code>{purchase['data']}</code>"
    )
    await safe_edit(callback, 
        text,
        reply_markup=copy_data_kb(purchase["data"], purchase_id)
    )
    await safe_answer(callback, )


@router.callback_query(F.data.startswith("copy_data:"))
async def copy_data_handler(callback: CallbackQuery):
    await safe_answer(callback, "✅ Данные скопированы!", show_alert=True)


@router.callback_query(F.data.startswith("request_code:"))
async def request_code_handler(callback: CallbackQuery):
    purchase_id = int(callback.data.split(":")[1])
    purchases = get_user_purchases(callback.from_user.id)
    purchase = next((p for p in purchases if p["id"] == purchase_id), None)

    if not purchase:
        await safe_answer(callback, "❌ Покупка не найдена", show_alert=True)
        return

    req_id = create_code_request(callback.from_user.id, purchase_id)
    add_log(callback.from_user.id, "code_request", f"purchase_id={purchase_id}, req_id={req_id}")

    from config import ADMIN_CHAT_ID, TOPIC_MONITORING
    if ADMIN_CHAT_ID:
        try:
            admin_text = (
                f"🔑 <b>Запрос кода 2FA</b>\n"
                f"👤 Пользователь: <code>{callback.from_user.id}</code>\n"
                f"🌍 Аккаунт: {purchase.get('country_name', 'N/A')}\n"
                f"📱 Тип: {'саморег' if purchase.get('account_type') == 'samoreg' else 'авторег'}\n"
                f"📅 Покупка #{purchase_id}\n"
                f"Запросил код для входа в аккаунт."
            )
            kwargs = {}
            if TOPIC_MONITORING:
                kwargs["message_thread_id"] = TOPIC_MONITORING
            await callback.bot.send_message(ADMIN_CHAT_ID, admin_text, parse_mode="HTML", **kwargs)
        except Exception:
            pass

    await safe_answer(callback, 
        "🔑 Запрос отправлен!\n"
        "Администратор получил уведомление и пришлёт код в ближайшее время.\n"
        "Ожидайте сообщение от бота.",
        show_alert=True
    )


@router.callback_query(F.data.startswith("reset_sessions:"))
async def reset_sessions_handler(callback: CallbackQuery):
    purchase_id = int(callback.data.split(":")[1])
    purchases = get_user_purchases(callback.from_user.id)
    purchase = next((p for p in purchases if p["id"] == purchase_id), None)

    if not purchase:
        await safe_answer(callback, "❌ Покупка не найдена", show_alert=True)
        return

    add_log(callback.from_user.id, "session_reset_request", f"purchase_id={purchase_id}")

    from config import ADMIN_CHAT_ID, TOPIC_MONITORING
    if ADMIN_CHAT_ID:
        try:
            admin_text = (
                f"🔄 <b>Запрос сброса сессий</b>\n"
                f"👤 Пользователь: <code>{callback.from_user.id}</code>\n"
                f"🌍 Аккаунт: {purchase.get('country_name', 'N/A')}\n"
                f"📱 Тип: {'саморег' if purchase.get('account_type') == 'samoreg' else 'авторег'}\n"
                f"📅 Покупка #{purchase_id}\n"
                f"⚡ <b>Действие:</b> Сбросить другие авторизации через LZT API\n"
                f"(terminate all sessions except current)\n"
                f"Если у вас есть доступ к item_id на LZT — выполните сброс."
            )
            kwargs = {}
            if TOPIC_MONITORING:
                kwargs["message_thread_id"] = TOPIC_MONITORING
            await callback.bot.send_message(ADMIN_CHAT_ID, admin_text, parse_mode="HTML", **kwargs)
        except Exception:
            pass

    await safe_answer(callback, 
        "🔄 Запрос на сброс сессий отправлен!\n"
        "Администратор выполнит сброс других авторизаций.\n"
        "Все старые сессии будут завершены — используйте только новые данные.",
        show_alert=True
    )


@router.callback_query(F.data.startswith("validate_acc:"))
async def validate_acc_handler(callback: CallbackQuery):
    purchase_id = int(callback.data.split(":")[1])
    purchases = get_user_purchases(callback.from_user.id)
    purchase = next((p for p in purchases if p["id"] == purchase_id), None)

    if not purchase:
        await safe_answer(callback, "❌ Покупка не найдена", show_alert=True)
        return

    add_log(callback.from_user.id, "validate_request", f"purchase_id={purchase_id}")

    from config import ADMIN_CHAT_ID, TOPIC_MONITORING
    if ADMIN_CHAT_ID:
        try:
            admin_text = (
                f"✅ <b>Запрос проверки валидности</b>\n"
                f"👤 Пользователь: <code>{callback.from_user.id}</code>\n"
                f"🌍 Аккаунт: {purchase.get('country_name', 'N/A')}\n"
                f"📱 Тип: {'саморег' if purchase.get('account_type') == 'samoreg' else 'авторег'}\n"
                f"📅 Покупка #{purchase_id}\n"
                f"⚡ <b>Действие:</b> Проверить валидность через LZT API (/validate)\n"
                f"Результат проверки отправьте пользователю."
            )
            kwargs = {}
            if TOPIC_MONITORING:
                kwargs["message_thread_id"] = TOPIC_MONITORING
            await callback.bot.send_message(ADMIN_CHAT_ID, admin_text, parse_mode="HTML", **kwargs)
        except Exception:
            pass

    await safe_answer(callback, 
        "✅ Запрос на проверку отправлен!\n"
        "Администратор проверит аккаунт и сообщит результат.\n"
        "Обычно это занимает до 10 минут.",
        show_alert=True
    )
