from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from tg_utils import safe_answer, safe_edit, send_safe_message
from database import get_user_purchases, get_account, create_code_request, get_pending_code_requests, update_code_request_status
from keyboards import copy_data_kb, back_to_main_kb
from lzt_api import reset_sessions_lzt, validate_account_lzt
from config import ADMIN_CHAT_ID
import logging

router = Router()

@router.callback_query(F.data == "my_purchases")
async def my_purchases(callback: CallbackQuery):
    user_id = callback.from_user.id
    purchases = get_user_purchases(user_id)
    if not purchases:
        text = "🛍 **Мои покупки**\nУ вас пока нет покупок."
        await safe_edit(callback, text, reply_markup=back_to_main_kb)
        await safe_answer(callback)
        return
    text = "🛍 **Мои покупки:**\n"
    for p in purchases:
        guarantee = "🛡 Пожизненная" if p.get("is_insured") else "🛡 24ч"
        text += f"• {p['country_name']} — {int(p['price'])}₽ — {guarantee}\n"
    await safe_edit(callback, text, reply_markup=back_to_main_kb)
    await safe_answer(callback)

@router.callback_query(F.data.startswith("copy_data:"))
async def copy_data_handler(callback: CallbackQuery):
    # FIX 13: используем purchase_id вместо данных в callback
    parts = callback.data.split(":")
    if len(parts) < 2:
        await safe_answer(callback, "❌ Неверные данные", show_alert=True)
        return
    try:
        purchase_id = int(parts[1])
    except (ValueError, TypeError):
        await safe_answer(callback, "❌ Неверный ID", show_alert=True)
        return
    purchases = get_user_purchases(callback.from_user.id)
    purchase = next((p for p in purchases if p["id"] == purchase_id), None)
    if not purchase:
        await safe_answer(callback, "❌ Покупка не найдена", show_alert=True)
        return
    account = get_account(purchase["account_id"])
    if not account:
        await safe_answer(callback, "❌ Данные недоступны", show_alert=True)
        return
    data = account.get("data", "")
    if not data:
        await safe_answer(callback, "❌ Данные пусты", show_alert=True)
        return
    text = (
        f"📋 **Данные аккаунта**\n"
        f"Страна: {purchase.get('country_name', 'N/A')}\n"
        f"Тип: {purchase.get('account_type', 'N/A')}\n"
        f"Цена: {int(purchase['price'])}₽\n\n"
        f"```{data}```"
    )
    await send_safe_message(callback.bot, text, chat_id=callback.from_user.id)
    await safe_answer(callback, "✅ Данные отправлены")

@router.callback_query(F.data.startswith("request_code:"))
async def request_code_handler(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) < 2:
        await safe_answer(callback, "❌ Неверные данные", show_alert=True)
        return
    try:
        purchase_id = int(parts[1])
    except (ValueError, TypeError):
        await safe_answer(callback, "❌ Неверный ID", show_alert=True)
        return
    purchases = get_user_purchases(callback.from_user.id)
    purchase = next((p for p in purchases if p["id"] == purchase_id), None)
    if not purchase:
        await safe_answer(callback, "❌ Покупка не найдена", show_alert=True)
        return
    req_id = create_code_request(callback.from_user.id, purchase_id)
    if ADMIN_CHAT_ID:
        try:
            await send_safe_message(callback.bot,
                f"🔑 **Запрос кода**\nUser: {callback.from_user.id}\nPurchase: {purchase_id}\nReq: {req_id}",
                chat_id=ADMIN_CHAT_ID)
        except Exception:
            pass
    await safe_answer(callback, f"✅ Запрос #{req_id} отправлен. Ожидайте ответа.", show_alert=True)

@router.callback_query(F.data.startswith("reset_sessions:"))
async def reset_sessions_handler(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) < 2:
        await safe_answer(callback, "❌ Неверные данные", show_alert=True)
        return
    try:
        purchase_id = int(parts[1])
    except (ValueError, TypeError):
        await safe_answer(callback, "❌ Неверный ID", show_alert=True)
        return
    purchases = get_user_purchases(callback.from_user.id)
    purchase = next((p for p in purchases if p["id"] == purchase_id), None)
    if not purchase:
        await safe_answer(callback, "❌ Покупка не найдена", show_alert=True)
        return
    account = get_account(purchase["account_id"])
    if not account or not account.get("data"):
        await safe_answer(callback, "❌ Невозможно сбросить сессии", show_alert=True)
        return
    await safe_answer(callback, "🔄 Сбрасываем сессии...")
    result = await reset_sessions_lzt(purchase_id)
    if result.get("error"):
        await safe_edit(callback, f"❌ Ошибка: {result['error']}", reply_markup=back_to_main_kb)
        return
    await safe_edit(callback, "✅ **Сессии сброшены!**\nПопробуйте войти снова.", reply_markup=back_to_main_kb)

@router.callback_query(F.data.startswith("validate_acc:"))
async def validate_acc_handler(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) < 2:
        await safe_answer(callback, "❌ Неверные данные", show_alert=True)
        return
    try:
        purchase_id = int(parts[1])
    except (ValueError, TypeError):
        await safe_answer(callback, "❌ Неверный ID", show_alert=True)
        return
    purchases = get_user_purchases(callback.from_user.id)
    purchase = next((p for p in purchases if p["id"] == purchase_id), None)
    if not purchase:
        await safe_answer(callback, "❌ Покупка не найдена", show_alert=True)
        return
    await safe_answer(callback, "🔄 Проверяем аккаунт...")
    result = await validate_account_lzt(purchase_id)
    if result.get("error"):
        await safe_edit(callback, f"❌ Ошибка проверки: {result['error']}", reply_markup=back_to_main_kb)
        return
    await safe_edit(callback, "✅ **Аккаунт валиден!**", reply_markup=back_to_main_kb)
