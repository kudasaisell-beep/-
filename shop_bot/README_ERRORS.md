# Полный аудит ошибок shop_bot

## 🔴 Критические (деньги / безопасность / потеря данных)

| # | Файл | Ошибка | Последствия | Исправлено |
|---|------|--------|-------------|------------|
| 1 | `buy.py` | `cancel_buy()` вызывался после `fast_buy()` при любой ошибке | Товар в статусе `paid` нельзя отменить — деньги с LZT списаны, пользователю не выдано | ✅ |
| 2 | `buy.py` | Баланс проверяется ДО `fast_buy()`, но списывается ПОСЛЕ через `purchase_account_tx()` | Между проверкой и покупкой баланс мог уйти в минус. `purchase_account_tx` откатится, но товар уже куплен на LZT — убыток | ⚠️ Частично (атомарность внутри tx) |
| 3 | `database.py` | `RETURNING id` в SQLite — не поддерживается в версиях <3.35 | `purchase_account_tx` и `add_account` падают на старых системах | ✅ |
| 4 | `database.py` | Connection leaks: `conn.close()` вне `finally` | При exception соединение не закрывается, итог — `database is locked` | ✅ |
| 5 | `database.py` | Нет `PRAGMA journal_mode=WAL` | При конкурентных запросах — `database is locked`, покупки падают | ✅ |
| 6 | `buy.py` | `user_pending_item` и `user_lzt_cart` — глобальные dict без TTL | Memory leak, переполнение RAM при долгой работе | ⚠️ Нужен Redis |
| 7 | `buy.py` | Double-click на insurance: `user_pending_item.pop()` для второго клика вернёт None, но `fast_buy` уже сработал | Двойная покупка одного товара или падение | ✅ (добавлена проверка) |
| 8 | `cart.py` | Частичная очистка корзины: `remove_cart_item` внутри цикла, если цикл падает — часть товаров удалена, часть нет | Потеря данных о корзине | ✅ (перенесено после успеха) |
| 9 | `lzt_api.py` | Каждый запрос создаёт новый `aiohttp.ClientSession()` | Утечка соединений, исчерпание файловых дескрипторов | ✅ |
| 10 | `lzt_api.py` | Нет обработки HTTP 429 Too Many Requests | LZT банит IP, все запросы падают | ✅ |
| 11 | `account_actions.py` | `reset_sessions` и `validate_acc` НЕ выполняют действие, а только шлют админу сообщение | Пользователь думает, что сброс произошёл, но нет | ✅ (добавлена проверка владельца + честное сообщение) |
| 12 | `account_actions.py` | Нет проверки владельца purchase | Любой пользователь мог запросить чужой аккаунт по ID | ✅ |
| 13 | `bot.py` | `_check_token` создаёт новый `asyncio.new_event_loop()` в синхронном контексте | Deadlock, конфликт с существующим loop | ✅ |
| 14 | `bot.py` | `signal_handler` lambda захватывает `sig` по ссылке | Всегда обрабатывает последний сигнал (SIGINT вместо SIGTERM) | ✅ |
| 15 | `start.py` | `get_db()` используется напрямую без `with` | Connection leak при exception в реферальной логике | ⚠️ |

## 🟠 Высокие (стабильность / надёжность)

| # | Файл | Ошибка | Последствия |
|---|------|--------|-------------|
| 16 | — | Нет `Dockerfile` | `docker-compose.yml` ссылается на `build: .`, сборка невозможна |
| 17 | — | Нет `requirements.txt` | Невозможно установить зависимости |
| 18 | `database.py` | `BEGIN EXCLUSIVE` блокирует всю БД SQLite | При 2+ одновременных покупках — очередь, таймауты |
| 19 | `keyboards.py` | `get_min_price()` вызывается для каждой страны при генерации клавиатуры | N+1 запросов, тормоза при открытии каталога |
| 20 | `tg_utils.py` | `safe_edit` отправляет новое сообщение при невозможности edit | Спам в чат при частых ошибках |
| 21 | `lzt_api.py` | `params` как list для GET-запросов | `aiohttp` не всегда корректно сериализует list в query string |
| 22 | `buy.py` | Нет проверки цены от `fast_buy` | LZT может списать другую сумму — убыток или недоплата |
| 23 | `admin.py` | `!поиск` — `items = await search_telegram_accounts(country=country_code)` без `account_type` | Возвращает оба типа, но `filtered` берёт `price` из `item.get("price")` — может быть string |
| 24 | `admin.py` | `cmd_test_buy` пишет в реальную БД через `add_account`/`update_account_status` | Засорение БД тестовыми данными |
| 25 | `config.py` | `print()` при импорте модуля | Если бот запущен как демон — `BrokenPipeError` |
| 26 | `redis_client.py` | `_redis_down_until` — глобальная переменная | При многопроцессности (не async) — race condition |
| 27 | `cleanup_logs.py` | `datetime.now()` без timezone | SQLite хранит local time, при смене TZ — некорректная очистка |
| 28 | `backup.sh` | `cp` без проверки существования `shop.db` | Ошибка cron, если БД перемещена |
| 29 | `setup.sh` | `ufw` и `certbot` без проверки установки | Падение скрипта на минимальных системах |
| 30 | `nginx.conf` | `limit_req_zone` внутри `server` | nginx не запустится, директива должна быть в `http` |

## 🟡 Средние (UX / логика)

| # | Файл | Ошибка | Последствия |
|---|------|--------|-------------|
| 31 | `keyboards.py` | `progress_kb` — кнопка с `callback_data="noop"` | Пользователь нажимает, видит "loading", ничего не происходит |
| 32 | `support.py` | FSM `ticket_type` может застрять | Пользователь застревает в состоянии, бот не отвечает |
| 33 | `balance.py` | `pay_stars_custom` — нет валидации ввода | Можно ввести "abc", бот упадёт или создаст некорректный инвойс |
| 34 | `reviews.py` | `has_user_reviewed` не проверяет покупку | Можно оставить отзыв без покупки |
| 35 | `referral.py` | `ref_earnings` начисляется, но нет вывода | Рефералы копят деньги, которые нельзя потратить |
| 36 | `info.py` | FAQ callback'и — текст может быть >4096 символов | `TelegramBadRequest: message is too long` |
| 37 | `legal.py` | Жёстко зашитый текст политики | Изменение требует перезапуска бота |
| 38 | `docker-compose.yml` | `depends_on` не ждёт готовности Redis | Бот стартует раньше Redis, падает с `Connection refused` |
| 39 | `bot.py` | `monitor_lzt_deals` — `__import__("random")` | Хак, замедляет выполнение |
| 40 | `buy.py` | `user_filters` — глобальный dict без cleanup | Memory leak |

## 🟢 Низкие (косметика / логи)

| # | Файл | Ошибка |
|---|------|--------|
| 41 | `database.py` | `seed_demo_accounts` — `conn.commit()` вне try/except |
| 42 | `bot.py` | `logging.basicConfig` после импорта sentry_client — ранние ошибки не попадают в Sentry |
| 43 | `config.py` | `BACKUP_BOT_TOKENS` — токены видны в .env (ок, но стоит упомянуть) |
| 44 | `test_lzt.py` | `LZT_TOKEN[:20]` при пустом токене — `IndexError` |
| 45 | `tg_validator.py` | `client.send_message("@SpamBot", "/start")` — может засветить валидную сессию |

---

## Что исправлено в этом ZIP

### database.py
- ✅ `DBConnection` context manager — гарантированное закрытие соединений
- ✅ `PRAGMA journal_mode=WAL` — конкурентность без блокировок
- ✅ `PRAGMA busy_timeout=5000` — автоматическое ожидание при locked
- ✅ `lastrowid` вместо `RETURNING id` — совместимость со старым SQLite
- ✅ `get_db_singleton()` — переиспользование соединения в основном потоке

### lzt_api.py
- ✅ Глобальная `aiohttp.ClientSession` — переиспользование соединений
- ✅ Обработка HTTP 429 — retry с `Retry-After` header
- ✅ Фикс `params` list → dict для корректной сериализации

### bot.py
- ✅ Async проверка токенов — убран `new_event_loop()` deadlock
- ✅ Исправлен `signal_handler` — lambda баг устранён
- ✅ Graceful shutdown — закрытие aiohttp session
- ✅ Убраны `__import__` хаки

### account_actions.py
- ✅ Проверка владельца purchase (`_is_purchase_owner`)
- ✅ Честные сообщения: автоматический сброс/валидация невозможны без `item_id`
- ✅ Уведомление админу с контекстом для ручной обработки

### buy.py / cart.py
- ✅ Убран `cancel_buy` из критического пути
- ✅ `get_item_secure_data` — получение данных ДО списания баланса
- ✅ При ошибке получения данных — НЕ списываем баланс, алерт админу

## Рекомендации

1. **Добавьте `item_id` в таблицу `purchases`** — тогда `reset_sessions` и `validate` смогут работать автоматически
2. **Перейдите на PostgreSQL** — SQLite не выдержит нагрузку >10 покупок/мин
3. **Добавьте `requirements.txt`**:
   ```
   aiogram==3.13.1
   aiohttp==3.10.10
   redis==5.0.8
   python-dotenv==1.0.1
   sentry-sdk==2.18.0
   telethon==1.37.0
   ```
4. **Добавьте `Dockerfile`**:
   ```dockerfile
   FROM python:3.11-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   COPY . .
   CMD ["python", "bot.py"]
   ```
5. **Добавьте Redis TTL для `user_pending_item`** — замените глобальные dict на Redis hash с TTL 300 сек
