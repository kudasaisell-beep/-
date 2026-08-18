# 🚀 Shop Bot v2 — Обновление каталога + Пополнение через карту

## Что изменено

1. **Главное меню**: кнопка "📋 Покупка аккаунта" → "🛒 Покупка"
2. **Категории товаров**: 💬 Мессенджеры, 🎮 Игры, 🎬 Сервисы
3. **Подкатегории**: Telegram, TikTok, Discord, Instagram, Twitter, VK, Reddit, Genshin, Minecraft, Steam, Fortnite, Valorant, Roblox, Epic Games, Spotify, Netflix, ChatGPT, Canva, YouTube, iCloud
4. **Фильтр нелегальных источников**: брут, фишинг, стиллер, hacked, stolen, cracked, checker, combo, database, leak, dump, logs — исключены для ВСЕХ категорий
5. **Полная информация из LZT**: при покупке выдаётся ВСЁ, что есть в raw-ответе API
6. **Пополнение через карту**: ввод суммы → карта 2200 7020 7997 0948 → скриншот чека → админу с кнопками Принять/Отклонить

---

## 📦 Установка

### Шаг 1: Замените файлы

```bash
cp keyboards.py /path/to/shop_bot/
cp lzt_api.py /path/to/shop_bot/
cp handlers/buy.py /path/to/shop_bot/handlers/
cp handlers/balance.py /path/to/shop_bot/handlers/
cp handlers/admin.py /path/to/shop_bot/handlers/
cp handlers/start.py /path/to/shop_bot/handlers/
```

### Шаг 2: Обновите database.py

Добавьте в `init_db()` таблицу `deposits` и функции из `database_updates_v2.py`.

### Шаг 3: Пересоздайте БД

```bash
python database.py
```

### Шаг 4: Перезапустите бота

```bash
python bot.py
```

---

## ⚠️ ОШИБКИ, КОТОРЫЕ МОГУТ ПОМЕШАТЬ ЗАПУСКУ ПРЯМО СЕЙЧАС

### 1. ❌ Отсутствуют функции в database.py
**Проблема**: `create_pending_purchase`, `finalize_pending_purchase`, `deduct_balance_only`, `refund_balance`, `check_rate_limit`, `create_deposit`, `get_deposit`, `update_deposit_status`

**Решение**: Проверьте, что эти функции реально существуют в вашем `database.py`. В оригинальном репозитории они используются в `buy.py`, но их реализация может отсутствовать или отличаться.

**Как проверить**:
```bash
grep -n "def create_pending_purchase" database.py
grep -n "def finalize_pending_purchase" database.py
grep -n "def deduct_balance_only" database.py
grep -n "def refund_balance" database.py
```

### 2. ❌ Отсутствует `tg_validator`
**Проблема**: `from tg_validator import validate_account` — если этого файла нет, бот упадёт при покупке Telegram-аккаунтов.

**Решение**: Создайте заглушку:
```python
# tg_validator.py
async def validate_account(session, login):
    return {"ok": True}
```

### 3. ❌ Отсутствует `tg_utils`
**Проблема**: `safe_answer`, `safe_edit`, `send_safe_message` импортируются из `tg_utils.py`.

**Решение**: Убедитесь, что `tg_utils.py` существует и содержит эти функции.

### 4. ❌ Redis не запущен
**Проблема**: `redis_client.py` используется для блокировок (`acquire_item_lock`, `set_user_cooldown`). Если Redis недоступен — покупки упадут.

**Решение**: Запустите Redis или создайте заглушки в `redis_client.py`:
```python
def acquire_item_lock(item_id, user_id): return True
def release_item_lock(item_id): pass
def set_user_cooldown(user_id, seconds): pass
def is_user_cooldown(user_id): return False
def check_redis_rate_limit(*args, **kwargs): return {"ok": True}
def is_purchases_paused(): return False
```

### 5. ❌ LZT API endpoints для других категорий
**Проблема**: `/tiktok`, `/discord`, `/genshin-impact` и т.д. могут не существовать на LZT или иметь другие пути.

**Решение**: Проверьте реальные endpoints в документации LZT API. В `lzt_api.py` в словаре `CATEGORY_ENDPOINTS` укажите правильные пути.

### 6. ❌ Нет прав на отправку фото в ADMIN_CHAT_ID
**Проблема**: При пополнении через карту бот пытается отправить фото (чек) в админ-чат. Если бот не состоит в группе или не имеет прав — упадёт.

**Решение**: Убедитесь, что `ADMIN_CHAT_ID` — это ID супергруппы, бот является админом и может отправлять фото.

### 7. ❌ FSM Storage (Redis) не настроен
**Проблема**: Новые состояния `CardDepositState` требуют FSM storage. Если Redis недоступен — состояния не будут работать.

**Решение**: В `bot.py` должен быть `RedisStorage.from_url(REDIS_URL)`.

### 8. ❌ Коллизия callback_data
**Проблема**: Новые callback_data могут конфликтовать со старыми хендлерами, если какие-то роутеры подключены дважды.

**Решение**: Убедитесь, что в `bot.py` нет дублирования `dp.include_router()`.

### 9. ❌ Неправильный ADMIN_CHAT_ID
**Проблема**: Если `ADMIN_CHAT_ID` не задан или задан как ID пользователя (а не группы), пересылка чеков не сработает.

**Решение**: `ADMIN_CHAT_ID` должен быть ID супергруппы (начинается с `-100`).

### 10. ❌ Отсутствуют колонки в таблице favorites
**Проблема**: Новый код использует `fav.get("subcat_key")`, но в оригинальной БД этой колонки нет.

**Решение**: Добавьте миграцию:
```sql
ALTER TABLE favorites ADD COLUMN subcat_key TEXT DEFAULT 'telegram';
```

### 11. ❌ Callback data > 64 байт
**Проблема**: Telegram ограничивает callback_data 64 байтами. Некоторые новые callback_data могут превышать лимит.

**Решение**: Проверьте длину всех callback_data. Например, `admin_deposit_accept:123:456789:1000` — 37 символов, это нормально.

### 12. ❌ Нет обработки `create_pending_purchase` / `finalize_pending_purchase`
**Проблема**: Если в вашей БД нет таблицы для pending_purchases — код упадёт.

**Решение**: Добавьте таблицу:
```sql
CREATE TABLE IF NOT EXISTS pending_purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    item_id INTEGER,
    price REAL,
    cost_price REAL,
    account_data TEXT,
    country_code TEXT,
    country_name TEXT,
    account_type TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🔧 Быстрая проверка перед запуском

```bash
# 1. Проверьте синтаксис
python -m py_compile bot.py
python -m py_compile handlers/buy.py
python -m py_compile handlers/balance.py
python -m py_compile handlers/admin.py
python -m py_compile lzt_api.py
python -m py_compile keyboards.py

# 2. Проверьте токен LZT
python test_lzt.py

# 3. Проверьте БД
python -c "from database import init_db; init_db(); print('OK')"

# 4. Проверьте Redis
python -c "from redis_client import is_purchases_paused; print('Redis OK')"
```

---

## 🎮 Админ-команды (остались без изменений)

| Команда | Описание |
|---------|----------|
| `!статистика [период]` | Статистика магазина |
| `!цена КОД ЦЕНА` | Установить цену |
| `!пользователь ID` | Инфо о пользователе |
| `!тикеты` | Открытые тикеты |
| `!возвраты` | Ожидающие возвраты |

---

## 💡 Рекомендации

1. **Тестируйте на копии** — перед деплоем на прод протестируйте на тестовом боте
2. **Бэкап БД** — сделайте бэкап `shop.db` перед миграциями
3. **Проверьте LZT токен** — убедитесь, что токен имеет доступ ко всем категориям
4. **Проверьте баланс LZT** — авто-закупка требует средств на балансе
5. **Мониторьте логи** — первые 24 часа после обновления смотрите логи на ошибки
