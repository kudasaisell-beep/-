#!/usr/bin/env python3
"""
Расширенный мониторинг баланса LZT.
Запускать: python lzt_balance_monitor.py &
Или через systemd.
"""
import asyncio
import logging
from datetime import datetime

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMIN_CHAT_ID, MIN_LZT_BALANCE, BOT_TOKEN
from redis_client import set_purchases_paused, is_purchases_paused
from lzt_api import get_lzt_balance
from database import add_log

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHECK_INTERVAL = 300  # 5 минут
CRITICAL_BALANCE = 500  # критический минимум


async def check_and_alert(bot):
    try:
        result = await get_lzt_balance()
        lzt_balance = 0.0
        user_info = {}
        if isinstance(result, dict):
            try:
                lzt_balance = float(result.get("balance", 0))
                user_info = result
            except (ValueError, TypeError):
                lzt_balance = 0.0

        logger.info(f"LZT balance: {lzt_balance} ₽")

        # Критически низкий баланс
        if lzt_balance < CRITICAL_BALANCE:
            if not is_purchases_paused():
                set_purchases_paused(True)
                logger.critical(f"CRITICAL: LZT balance {lzt_balance} ₽")

                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Пополнить LZT", url="https://lzt.market/balance")],
                    [InlineKeyboardButton(text="▶️ Возобновить продажи", callback_data="resume_sales")],
                ])

                if ADMIN_CHAT_ID:
                    await bot.send_message(
                        ADMIN_CHAT_ID,
                        f"🚨 <b>КРИТИЧЕСКИ НИЗКИЙ БАЛАНС LZT!</b>\n\n"
                        f"Текущий баланс: <b>{lzt_balance} ₽</b>\n"
                        f"Критический минимум: <b>{CRITICAL_BALANCE} ₽</b>\n\n"
                        f"🛑 <b>Продажи ОСТАНОВЛЕНЫ</b>\n"
                        f"Пополните баланс и нажмите «Возобновить продажи».",
                        reply_markup=kb,
                        parse_mode="HTML"
                    )
                add_log(0, "lzt_critical", f"balance={lzt_balance}")

        # Низкий баланс (предупреждение)
        elif lzt_balance < MIN_LZT_BALANCE:
            if not is_purchases_paused():
                logger.warning(f"Low LZT balance: {lzt_balance} ₽")
                if ADMIN_CHAT_ID:
                    await bot.send_message(
                        ADMIN_CHAT_ID,
                        f"⚠️ <b>Баланс LZT на исходе</b>\n\n"
                        f"Текущий: <b>{lzt_balance} ₽</b>\n"
                        f"Минимум: <b>{MIN_LZT_BALANCE} ₽</b>\n\n"
                        f"Рекомендуется пополнить в ближайшее время.",
                        parse_mode="HTML"
                    )
                add_log(0, "lzt_warning", f"balance={lzt_balance}")

        # Баланс восстановлен
        else:
            if is_purchases_paused():
                set_purchases_paused(False)
                logger.info(f"LZT balance restored: {lzt_balance} ₽")
                if ADMIN_CHAT_ID:
                    await bot.send_message(
                        ADMIN_CHAT_ID,
                        f"✅ <b>Баланс LZT в норме</b>\n\n"
                        f"Текущий: <b>{lzt_balance} ₽</b>\n"
                        f"Продажи возобновлены автоматически.",
                        parse_mode="HTML"
                    )
                add_log(0, "lzt_restored", f"balance={lzt_balance}")

    except Exception as e:
        logger.error(f"Balance monitor error: {e}")


async def monitor_loop(bot):
    while True:
        await check_and_alert(bot)
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        asyncio.run(monitor_loop(bot))
    except KeyboardInterrupt:
        logger.info("Balance monitor stopped")
