#!/usr/bin/env python3
"""
UptimeRobot alternative — самостоятельный мониторинг /health.
Запускать: python uptime_monitor.py &
Или через systemd: uptime-monitor.service
"""
import asyncio
import aiohttp
import logging
import os
from datetime import datetime

from config import ADMIN_CHAT_ID, WEBHOOK_URL
from database import get_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHECK_INTERVAL = 300  # 5 минут
HEALTH_URL = WEBHOOK_URL.replace("/webhook", "/health") if WEBHOOK_URL else "http://localhost:8080/health"


async def check_health(bot):
    """Проверяет /health и шлёт алерт если бот упал."""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(HEALTH_URL) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("purchases_paused"):
                        logger.warning("Purchases are paused (low LZT balance)")
                    else:
                        logger.info("Health check OK")
                    return True
                else:
                    raise Exception(f"HTTP {resp.status}")
    except Exception as e:
        error_msg = (
            f"🚨 <b>БОТ НЕДОСТУПЕН!</b>\n\n"
            f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"URL: {HEALTH_URL}\n"
            f"Ошибка: {str(e)[:200]}\n\n"
            f"Проверьте сервер немедленно!"
        )
        logger.error(f"Health check failed: {e}")
        if ADMIN_CHAT_ID:
            try:
                await bot.send_message(ADMIN_CHAT_ID, error_msg, parse_mode="HTML")
            except Exception as send_err:
                logger.error(f"Failed to send alert: {send_err}")
        return False


async def monitor_loop(bot):
    while True:
        await check_health(bot)
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from config import BOT_TOKEN

    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set!")
        exit(1)

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        asyncio.run(monitor_loop(bot))
    except KeyboardInterrupt:
        logger.info("Monitor stopped")
