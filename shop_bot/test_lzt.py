import asyncio
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()

LZT_TOKEN = os.getenv("LZT_TOKEN", "")
BASE_URL = "https://prod-api.lzt.market"
HEADERS = {"Authorization": f"Bearer {LZT_TOKEN}"}

async def test_lzt():
    print("=" * 50)
    print("ПРОВЕРКА ПОДКЛЮЧЕНИЯ К LZT.MARKET")
    print("=" * 50)

    if not LZT_TOKEN:
        print("\n❌ ОШИБКА: LZT_TOKEN не найден в .env!")
        print("   Добавьте токен в файл .env и запустите снова.")
        return

    print(f"\n🔑 Токен найден: {LZT_TOKEN[:20]}...{LZT_TOKEN[-10:]}")

    # Test 1: Search accounts
    print("\n📡 Тест 1: Поиск Telegram-аккаунтов (страна: US, авторег)...")
    try:
        async with aiohttp.ClientSession() as session:
            params = [
                ("page", "1"),
                ("nsb", "1"),
                ("order_by", "price_to_up"),
                ("spam", "no"),
                ("password", "no"),
                ("currency", "rub"),
                ("country[]", "US"),
                ("origin[]", "autoreg"),  # origin[] исключает phishing/stealer
            ]
            async with session.get(f"{BASE_URL}/telegram", headers=HEADERS, params=params, timeout=15) as resp:
                print(f"   Статус ответа: {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get("items", [])
                    total = data.get("totalItems", len(items))
                    print(f"   ✅ УСПЕХ! Найдено аккаунтов: {len(items)} (всего: {total})")
                    if items:
                        first = items[0]
                        print(f"   📦 Первый аккаунт: {first.get('title', 'N/A')} — {first.get('price', 'N/A')}₽")
                        print(f"   🧬 Происхождение (origin): {first.get('item_origin', 'N/A')}")
                        origins = {it.get("item_origin") for it in items}
                        bad = origins & {"phishing", "stealer"}
                        if bad:
                            print(f"   ⚠️ ВНИМАНИЕ: в выдаче есть запрещённые origin: {bad}")
                        else:
                            print("   🛡 Фишинг/стиллер в выдаче отсутствуют")
                elif resp.status == 401:
                    print("   ❌ ОШИБКА 401: Токен невалидный или истёк!")
                    text = await resp.text()
                    print(f"   Ответ: {text[:200]}")
                else:
                    text = await resp.text()
                    print(f"   ❌ ОШИБКА {resp.status}: {text[:200]}")
    except Exception as e:
        print(f"   ❌ ИСКЛЮЧЕНИЕ: {e}")

    # Test 2: Check balance
    print("\n📡 Тест 2: Проверка баланса LZT...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/me", headers=HEADERS, timeout=15) as resp:
                print(f"   Статус ответа: {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    user = data.get("user", {})
                    balance = user.get("balance", "N/A")
                    user_id = user.get("user_id", "N/A")
                    print(f"   ✅ УСПЕХ! User ID: {user_id}, Баланс: {balance}₽")
                elif resp.status == 401:
                    print("   ❌ ОШИБКА 401: Токен невалидный!")
                else:
                    text = await resp.text()
                    print(f"   ❌ ОШИБКА {resp.status}: {text[:200]}")
    except Exception as e:
        print(f"   ❌ ИСКЛЮЧЕНИЕ: {e}")

    print("\n" + "=" * 50)
    print("ПРОВЕРКА ЗАВЕРШЕНА")
    print("=" * 50)

if __name__ == "__main__":
    if not LZT_TOKEN:
        print("\n" + "="*50)
        print("❌ ОШИБКА: LZT_TOKEN не найден в .env!")
        print("   Скопируй .env.example → .env и заполни LZT_TOKEN")
        print("="*50 + "\n")
        exit(1)
    asyncio.run(test_lzt())
