from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from tg_utils import safe_answer, safe_edit, send_safe_message
from database import (
    get_cart, clear_cart, remove_cart_item, get_user, add_purchase, 
    update_account_status, add_log, get_account, deduct_balance_only, 
    refund_balance, create_pending_purchase, finalize_pending_purchase
)
from keyboards import cart_kb, back_to_main_kb, back_to_buy_kb
from config import ADMIN_CHAT_ID, TOPIC_PURCHASES, USER_BUY_COOLDOWN
from redis_client import is_purchases_paused, set_user_cooldown, is_user_cooldown, check_redis_rate_limit
from lzt_api import reserve_item, confirm_buy, get_item_secure_data, cancel_buy
from tg_validator import validate_account
import asyncio

router = Router()

_cart_locks: dict[int, asyncio.Lock] = {}

def _get_user_lock(user_id: int) -> asyncio.Lock:
    if user_id not in _cart_locks:
        _cart_locks[user_id] = asyncio.Lock()
    return _cart_locks[user_id]

@router.callback_query(F.data == "cart")
async def show_cart(callback: CallbackQuery):
    user_id = callback.from_user.id
    items = get_cart(user_id)
    if not items:
        text = "🛒 **Корзина**\nКорзина пуста."
        await safe_edit(callback, text, reply_markup=back_to_buy_kb)
        await safe_answer(callback)
        return
    text = _build_cart_text(items)
    await safe_edit(callback, text, reply_markup=cart_kb(items))
    await safe_answer(callback)

def _build_cart_text(items):
    text = "🛒 **Ваша корзина:**\n"
    total = 0.0
    for item in items:
        text += f"• {item['country_name']} — {int(item['price'])}₽\n"
        total += float(item["price"])
    text += f"\n💰 **Итого:** {int(total)}₽"
    return text

@router.callback_query(F.data.startswith("remove_cart:"))
async def remove_cart_item_handler(callback: CallbackQuery):
    cart_id = int(callback.data.split(":")[1])
    remove_cart_item(cart_id)
    await safe_answer(callback, "✅ Удалено из корзины")
    # FIX 28: recalc and show updated cart
    items = get_cart(callback.from_user.id)
    if not items:
        await safe_edit(callback, "🛒 **Корзина**\nКорзина пуста.", reply_markup=back_to_buy_kb)
        return
    text = _build_cart_text(items)
    await safe_edit(callback, text, reply_markup=cart_kb(items))

@router.callback_query(F.data == "clear_cart")
async def clear_cart_handler(callback: CallbackQuery):
    clear_cart(callback.from_user.id)
    await safe_answer(callback, "✅ Корзина очищена")
    await safe_edit(callback, "🛒 **Корзина**\nКорзина пуста.", reply_markup=back_to_buy_kb)

@router.callback_query(F.data == "checkout")
async def checkout(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with _get_user_lock(user_id):
        items = get_cart(user_id)
        if not items:
            await safe_answer(callback, "❌ Корзина пуста", show_alert=True)
            return

        # FIX 3: deduplicate item_id
        seen_item_ids = set()
        unique_items = []
        for it in items:
            iid = it.get("item_id")
            if iid:
                if iid in seen_item_ids:
                    continue
                seen_item_ids.add(iid)
            unique_items.append(it)
        items = unique_items

        if is_purchases_paused():
            await safe_answer(callback, "🛑 Покупки приостановлены.", show_alert=True)
            return

        user = get_user(user_id)
        # FIX 28: recalc total after dedup
        total = sum(float(it["price"]) for it in items)
        if not user or user["balance"] < total:
            bal = user["balance"] if user else 0
            await safe_answer(callback, f"❌ Недостаточно средств. Баланс: {int(bal)}₽", show_alert=True)
            return
        if is_user_cooldown(user_id):
            await safe_answer(callback, f"⏱ Подождите {USER_BUY_COOLDOWN} сек", show_alert=True)
            return

        # FIX 31: rate limit
        rl = check_redis_rate_limit(user_id, "buy", max_count=5, window_seconds=60)
        if not rl["ok"]:
            await safe_answer(callback, f"⏱ Слишком много покупок. Подождите {rl['retry_after']} сек.", show_alert=True)
            return

        # Списываем баланс заранее
        deduct = deduct_balance_only(user_id, total)
        if not deduct["ok"]:
            await safe_answer(callback, f"❌ {deduct.get('error')}", show_alert=True)
            return

        purchased = []
        failed = 0
        for item in items:
            item_id = item.get("item_id")
            price = float(item["price"])
            cost_price = float(item.get("cost_price", price * 0.5))
            country_code = item.get("country_code", "")
            country_name = item.get("country_name", "")
            account_type = item.get("account_type", "samoreg")

            # FIX 24: handle None item_id
            if item_id is None:
                account_id = item.get("account_id")
                if not account_id:
                    failed += 1
                    continue
                account = get_account(account_id)
                if not account or account["status"] != "available":
                    failed += 1
                    continue
                update_account_status(account_id, "sold")
                add_purchase(user_id, account_id, price, guarantee_hours=24, is_insured=False)
                add_log(user_id, "buy_cart", f"account_id={account_id}, price={price}")
                purchased.append(account)
                continue

            # LZT покупка
            reserve = await reserve_item(item_id)
            if reserve.get("error") or not reserve.get("status"):
                failed += 1
                continue

            data_result = await get_item_secure_data(item_id)
            login = data_result.get("login", "")
            password = data_result.get("password", "")
            session = data_result.get("session", "")
            has_2fa = data_result.get("2fa", False)

            if data_result.get("error") or not login or not session:
                await cancel_buy(item_id)
                failed += 1
                continue

            validation = await validate_account(session, login)
            if not validation["ok"]:
                await cancel_buy(item_id)
                failed += 1
                continue

            confirm = await confirm_buy(item_id)
            if confirm.get("error"):
                await cancel_buy(item_id)
                failed += 1
                continue

            # FIX 23: verify
            verify = await verify_purchase(item_id)
            if not verify["ok"]:
                await cancel_buy(item_id)
                failed += 1
                continue

            account_data = f"Телефон: {login}\nПароль: {password}\nСессия: {session}"
            if has_2fa:
                account_data += "\n⚠️ На аккаунте включен 2FA"

            pending_id = create_pending_purchase(user_id, item_id, price, cost_price, account_data,
                                                 country_code, country_name, account_type)
            tx = finalize_pending_purchase(
                pending_id, user_id, price, cost_price, account_data,
                country_code, country_name, account_type,
                item_age_days=item.get("item_age_days"),
                has_avatar=item.get("has_avatar", False),
                reg_date=item.get("reg_date"),
                contacts_count=item.get("contacts_count"),
                has_premium=item.get("has_premium", False)
            )
            if not tx["ok"]:
                failed += 1
                if ADMIN_CHAT_ID:
                    await send_safe_message(callback.bot,
                        f"🚨 Ошибка БД (корзина): {tx.get('error')}\nItem ID: {item_id}\nUser: {user_id}",
                        chat_id=ADMIN_CHAT_ID)
                continue

            purchased.append({
                "country_name": country_name,
                "price": price,
                "data": account_data,
            })

        clear_cart(user_id)
        if not purchased:
            refund_balance(user_id, total)
            await safe_edit(callback, "❌ **Покупка не удалась**\nНе удалось выкупить ни одного аккаунта.", reply_markup=back_to_main_kb)
            return

        # FIX 28: recalc actual total
        actual_total = sum(float(p["price"]) for p in purchased)
        if actual_total < total:
            refund_balance(user_id, total - actual_total)

        set_user_cooldown(user_id, USER_BUY_COOLDOWN)
        add_log(user_id, "checkout", f"items={len(purchased)}, total={actual_total}")

        if ADMIN_CHAT_ID:
            text = (
                f"🛒 **Покупка из корзины!**\n"
                f"👤 Пользователь: `{user_id}`\n"
                f"📦 Количество: {len(purchased)} шт" + (f" ({failed} не удалось)" if failed else "") + "\n"
                f"💰 Сумма: {int(actual_total)}₽"
            )
            kwargs = {}
            if TOPIC_PURCHASES:
                kwargs["message_thread_id"] = TOPIC_PURCHASES
            await send_safe_message(callback.bot, text, chat_id=ADMIN_CHAT_ID, **kwargs)

        result_text = "✅ **Покупка из корзины успешна!**" + (f"\n⚠️ {failed} акк. не удалось" if failed else "") + "\n\n"
        for idx, p in enumerate(purchased, 1):
            result_text += f"**{idx}.** {p['country_name']} — {int(p['price'])}₽\n"
            result_text += f" `{p['data']}`\n\n"
        result_text += "Сохраните данные — они больше не будут показаны."
        await safe_edit(callback, result_text, reply_markup=back_to_main_kb)
