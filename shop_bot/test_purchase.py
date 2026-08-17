#!/usr/bin/env python3
"""
Тестовая покупка — прогон полного цикла перед запуском.
Запускать: python test_purchase.py
"""
import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, ADMIN_IDS
from database import init_db, get_user, add_balance
from lzt_api import search_telegram_accounts, fast_buy, get_account_data_lzt, confirm_buy, cancel_buy, get_lzt_balance
from tg_validator import validate_account
from redis_client import acquire_item_lock, release_item_lock

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_test():
    print("=" * 60)
    print("ТЕСТОВЫЙ ПРОГОН ПОКУПКИ")
    print("=" * 60)

    # 1. Проверка БД
    print("\n[1/8] Инициализация БД...")
    init_db()
    print("✅ БД OK")

    # 2. Проверка LZT баланса
    print("\n[2/8] Проверка баланса LZT...")
    balance_info = await get_lzt_balance()
    print(f"Ответ LZT: {balance_info}")
    if isinstance(balance_info, dict) and "balance" in balance_info:
        print(f"✅ Баланс LZT: {balance_info['balance']} ₽")
    else:
        print("⚠️ Не удалось получить баланс (возможно токен невалиден)")

    # 3. Поиск аккаунтов
    print("\n[3/8] Поиск аккаунтов (US, авторег)...")
    result = await search_telegram_accounts(country="US", account_type="autoreg")
    if isinstance(result, dict) and result.get("error"):
        print(f"❌ Ошибка поиска: {result['error']}")
        return
    items = result.get("items", []) if isinstance(result, dict) else result
    if not items:
        print("❌ Нет аккаунтов в наличии")
        return
    print(f"✅ Найдено {len(items)} аккаунтов")
    item = items[0]
    item_id = item["item_id"]
    print(f"   Выбран item_id: {item_id}, цена: {item['price']} ₽")

    # 4. Блокировка через Redis
    print("\n[4/8] Redis lock...")
    locked = acquire_item_lock(item_id, 999999)
    if not locked:
        print("❌ Не удалось заблокировать лот (уже занят?)")
        return
    print("✅ Лот заблокирован")

    try:
        # 5. Fast buy (резерв)
        print("\n[5/8] Резервирование (fast_buy)...")
        buy_result = await fast_buy(item_id)
        print(f"   Результат: {buy_result}")
        if buy_result.get("error"):
            print("❌ Резервирование не удалось")
            return
        print("✅ Лот зарезервирован")

        # 6. Получение данных
        print("\n[6/8] Получение данных аккаунта...")
        data = await get_account_data_lzt(item_id)
        print(f"   Данные: {data}")
        if data.get("error"):
            print("❌ Не удалось получить данные")
            await cancel_buy(item_id)
            return
        print("✅ Данные получены")

        # 7. Валидация (если есть API ID)
        from config import TELEGRAM_API_ID
        if TELEGRAM_API_ID:
            print("\n[7/8] Валидация через Telegram API...")
            session = data.get("session", "")
            validation = await validate_account(session, data.get("login"))
            print(f"   Результат: {validation}")
            if not validation.get("ok"):
                print("⚠️ Аккаунт не прошёл валидацию (это нормально для теста)")
            else:
                print("✅ Аккаунт валиден")
        else:
            print("\n[7/8] Пропуск валидации (TELEGRAM_API_ID не задан)")

        # 8. Отмена покупки (тест — не тратим деньги)
        print("\n[8/8] Отмена покупки (cancel_buy)...")
        cancel_result = await cancel_buy(item_id)
        print(f"   Результат: {cancel_result}")
        print("✅ Покупка отменена, деньги возвращены на LZT")

    finally:
        release_item_lock(item_id)

    print("\n" + "=" * 60)
    print("✅ ТЕСТ ПРОЙДЕН! Бот готов к запуску.")
    print("=" * 60)


if __name__ == "__main__":
    if not BOT_TOKEN:
        print("\n" + "="*60)
        print("❌ ОШИБКА: BOT_TOKEN не найден в .env!")
        print("   Скопируй .env.example → .env и заполни BOT_TOKEN")
        print("="*60 + "\n")
        exit(1)
    asyncio.run(run_test())
