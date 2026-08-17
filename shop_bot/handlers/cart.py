from aiogram import Router, F
from tg_utils import safe_answer, safe_edit
from aiogram.types import CallbackQuery

from database import (
    get_cart, clear_cart, remove_cart_item, get_user, get_account,
    purchase_account_tx, purchase_existing_account_tx, add_log
)
from keyboards import cart_kb, back_to_main_kb, progress_kb, post_purchase_kb
from lzt_api import fast_buy, get_account_data_lzt, confirm_buy, cancel_buy
from redis_client import is_purchases_paused, acquire_item_lock, release_item_lock
from config import ADMIN_CHAT_ID, TOPIC_PURCHASES

router = Router()


def _type_label(account_type: str) -> str:
    return "саморег" if account_type == "samoreg" else "авторег"


def _build_cart_text(items) -> str:
    total = sum(item["price"] or 0 for item in items)
    text = (
        f"🛒 <b>Корзина</b>\n\n"
        f"Товаров: <b>{len(items)}</b>\n"
        f"Итого: <b>{int(total)}₽</b>\n"
        f"━━━━━━━━━━━━━━━\n"
    )
    for item in items:
        text += (
            f"• {item['country_name']} — {_type_label(item.get('account_type') or 'autoreg')} "
            f"— <b>{int(item['price'] or 0)}₽</b>\n"
        )
    text += "\nНажмите на товар, чтобы убрать его из корзины."
    return text


async def _notify_admin(bot, text: str):
    if ADMIN_CHAT_ID:
        try:
            kwargs = {}
            if TOPIC_PURCHASES:
                kwargs["message_thread_id"] = TOPIC_PURCHASES
            await bot.send_message(ADMIN_CHAT_ID, text, parse_mode="HTML", **kwargs)
        except Exception:
            pass


@router.callback_query(F.data == "cart")
async def cart_handler(callback: CallbackQuery):
    items = get_cart(callback.from_user.id)
    if not items:
        text = (
            "🛒 <b>Корзина</b>\n\n"
            "Ваша корзина пуста.\n"
            "Добавляйте аккаунты кнопкой «🛒 В корзину» в карточке товара."
        )
        await safe_edit(callback, text, reply_markup=back_to_main_kb)
        await safe_answer(callback, )
        return

    await safe_edit(callback, _build_cart_text(items), reply_markup=cart_kb(items))
    await safe_answer(callback, )


@router.callback_query(F.data.startswith("remove_cart:"))
async def remove_cart(callback: CallbackQuery):
    cart_id = int(callback.data.split(":")[1])
    remove_cart_item(cart_id)
    await safe_answer(callback, "✅ Удалено из корзины")
    await cart_handler(callback)


@router.callback_query(F.data == "clear_cart")
async def clear_cart_handler(callback: CallbackQuery):
    clear_cart(callback.from_user.id)
    await safe_edit(callback, 
        "🗑 <b>Корзина очищена.</b>",
        reply_markup=back_to_main_kb
    )
    await safe_answer(callback, )


@router.callback_query(F.data == "checkout")
async def checkout(callback: CallbackQuery):
    user_id = callback.from_user.id
    items = get_cart(user_id)
    if not items:
        await safe_answer(callback, "❌ Корзина пуста", show_alert=True)
        return

    if is_purchases_paused():
        await safe_answer(callback, 
            "🛑 Покупки временно приостановлены.\n"
            "Ведутся технические работы. Попробуйте позже.",
            show_alert=True
        )
        return

    total = sum(item["price"] or 0 for item in items)
    user = get_user(user_id)
    if not user or user["balance"] < total:
        bal = user["balance"] if user else 0
        await safe_answer(callback, 
            f"❌ Недостаточно средств. Баланс: {int(bal)}₽, нужно: {int(total)}₽",
            show_alert=True
        )
        return

    await safe_answer(callback, "⏳ Оформляем заказ...")
    await safe_edit(callback, 
        "⏳ <b>Оформление заказа...</b>\n" + progress_kb(1).inline_keyboard[0][0].text,
        reply_markup=progress_kb(1)
    )

    purchased = []      # (item, account_data)
    failed = []         # item
    spent = 0.0

    for item in items:
        price = item["price"] or 0
        account_data = None

        if item.get("item_id"):
            # Лот из каталога: блокировка → резерв → данные → подтверждение
            item_id = item["item_id"]

            if not acquire_item_lock(item_id, user_id):
                failed.append(item)
                continue

            buy_result = await fast_buy(item_id)
            if buy_result.get("error") or not buy_result.get("status"):
                release_item_lock(item_id)
                failed.append(item)
                continue

            data_result = await get_account_data_lzt(item_id)
            if data_result.get("error"):
                await cancel_buy(item_id)
                release_item_lock(item_id)
                failed.append(item)
                continue

            login = data_result.get("login", "N/A")
            password = data_result.get("password", "N/A")
            session = data_result.get("session", "N/A")
            has_2fa = data_result.get("2fa", False)

            if login == "N/A" or not session or session == "N/A":
                await cancel_buy(item_id)
                release_item_lock(item_id)
                failed.append(item)
                continue

            confirm_result = await confirm_buy(item_id)
            if confirm_result.get("error"):
                await cancel_buy(item_id)
                release_item_lock(item_id)
                failed.append(item)
                continue

            account_data = (
                f"Телефон: {login}\n"
                f"Пароль: {password}\n"
                f"Сессия: {session}"
            )
            if has_2fa:
                account_data += "\n⚠️ На аккаунте включен 2FA"

            tx = purchase_account_tx(
                user_id=user_id,
                account_id=0,
                price=price,
                cost_price=item.get("cost_price") or 0,
                account_data=account_data,
                country_code=item.get("country_code") or "",
                country_name=item.get("country_name") or "",
                account_type=item.get("account_type") or "autoreg",
                item_age_days=item.get("item_age_days"),
                has_avatar=bool(item.get("has_avatar")),
                reg_date=item.get("reg_date"),
                contacts_count=item.get("contacts_count"),
                has_premium=bool(item.get("has_premium")),
                guarantee_hours=24,
                is_insured=False,
            )
            if not tx["ok"]:
                await cancel_buy(item_id)
                release_item_lock(item_id)
                failed.append(item)
                continue

        elif item.get("account_id"):
            # Позиция из внутренней базы аккаунтов
            account = get_account(item["account_id"])
            if not account or account["status"] != "available":
                failed.append(item)
                continue

            tx = purchase_existing_account_tx(user_id, item["account_id"], price)
            if not tx["ok"]:
                failed.append(item)
                continue

            account_data = account["data"]

        else:
            failed.append(item)
            continue

        purchased.append((item, account_data))
        spent += price
        remove_cart_item(item["id"])

    if not purchased:
        await safe_edit(callback, 
            "❌ <b>Не удалось оформить заказ</b>\n"
            "Возможно, товары уже купили другие.\n"
            "Позиции остались в корзине — попробуйте позже.",
            reply_markup=back_to_main_kb
        )
        await safe_answer(callback, )
        return

    add_log(user_id, "cart_checkout", f"items={len(purchased)}, total={spent}, failed={len(failed)}")

    admin_text = (
        f"🛒 <b>Заказ из корзины!</b>\n"
        f"👤 Пользователь: <code>{user_id}</code>\n"
        f"📦 Позиций: {len(purchased)}" + (f" ({len(failed)} не удалось)" if failed else "") + "\n"
        f"💰 Сумма: {int(spent)}₽"
    )
    await _notify_admin(callback.bot, admin_text)

    result_text = (
        f"✅ <b>Заказ оформлен!</b>" + (f"\n⚠️ {len(failed)} позиц. не удалось выкупить — они остались в корзине" if failed else "") + "\n\n"
        f"📦 Куплено аккаунтов: <b>{len(purchased)}</b>\n"
        f"💰 Списано: <b>{int(spent)}₽</b>\n"
        f"🛡 Гарантия: 24 часа\n\n"
        f"Данные аккаунтов:\n"
    )
    for idx, (item, data) in enumerate(purchased, 1):
        result_text += (
            f"<b>{idx}. {item['country_name']} — {_type_label(item.get('account_type') or 'autoreg')}</b>\n"
            f"<code>{data}</code>\n\n"
        )
    result_text += "💾 Сохраните данные — они больше не будут показаны."

    await safe_edit(callback, result_text, reply_markup=post_purchase_kb)
    await safe_answer(callback, )
