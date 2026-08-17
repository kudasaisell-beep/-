# Telegram Accounts Shop Bot — Production Ready

Магазин Telegram-аккаунтов на aiogram 3.x с полной автоматизацией.

## 🛠 Что исправлено в этой версии

1. **Ошибка «Bad Request: query is too old and response timeout expired or query ID is invalid» (Bot Error).**
   Причина: бот отвечал на callback query ПОСЛЕ долгих операций (поиск/выкуп на LZT — 3–60+ сек),
   а Telegram требует ответ за ~15 секунд. Исправлено:
   - новый модуль `tg_utils.py` — `safe_answer()` / `safe_edit()`, не роняют хендлер на протухших query;
   - все хендлеры переведены на безопасные обёртки;
   - в `select_type` (загрузка карточек) бот отвечает на кнопку мгновенно, до поиска.
2. **Покупка без списания баланса (критично!).** В оптовой покупке `buy_lzt` и в `buy_account`
   баланс проверялся, но не списывался — аккаунты уходили бесплатно. Теперь оба потока
   используют атомарные транзакции `purchase_account_tx` / `purchase_existing_account_tx`.
3. **Резервирование лотов.** Подключены Redis-блокировки (`acquire_item_lock`) — два покупателя
   больше не могут одновременно выкупить один и тот же аккаунт. При любой ошибке лот
   отменяется (`cancel_buy`) и блокировка снимается.
4. **Антиспам покупок.** Задействован `USER_BUY_COOLDOWN` (10 сек между покупками).
5. **Реферальная программа.** Хендлер `/start ref...` был мёртвым кодом (дубль в referral.py
   никогда не вызывался) — логика перенесена в `start.py`. Исправлены SQL-плейсхолдеры
   `%s` → `?` (sqlite3) в balance.py/referral.py — реферальные бонусы больше не падают.
6. **Документы.** Добавлены 📜 «Политика конфиденциальности» и «Пользовательское соглашение»
   (новый хендлер `handlers/legal.py`, кнопки в главном меню и поддержке).

Магазин Telegram-аккаунтов на aiogram 3.x с полной автоматизацией.

## ⚡ Быстрый старт

```bash
# 1. Клонируй и настрой .env
cp .env.example .env
# Отредактируй все поля (BOT_TOKEN, LZT_TOKEN, ADMIN_ID и т.д.)

# 2. Docker (рекомендуется)
docker-compose up -d

# 3. Инициализация БД
docker-compose exec bot python database.py

# 4. Проверка LZT токена
docker-compose exec bot python test_lzt.py
```

## 🔧 Ручной запуск (без Docker)

```bash
pip install -r requirements.txt
cp .env.example .env
# Заполни .env
python database.py      # Создать таблицы
python test_lzt.py      # Проверить LZT токен
python bot.py           # Запустить бота
```

## 📁 Структура

```
shop_bot/
├── bot.py                 # Точка входа, webhook
├── config.py              # Конфигурация из .env
├── database.py            # PostgreSQL + транзакции
├── lzt_api.py             # LZT.market API (rate limit, retry)
├── redis_client.py        # Redis locks + cooldowns + purchases_paused
├── tg_validator.py        # Telethon валидация сессий
├── sentry_client.py       # Sentry (graceful при 403)
├── keyboards.py           # Все inline-клавиатуры
├── cleanup_logs.py        # Очистка старых логов по cron
├── requirements.txt
├── docker-compose.yml
├── nginx.conf
├── setup.sh               # Автоматическая настройка сервера
├── backup.sh
├── .env.example           # Шаблон конфигурации
├── .github/workflows/
│   └── deploy.yml         # CI/CD авто-деплой
├── handlers/
│   ├── start.py
│   ├── buy.py             # Каталог + избранное + добавление в корзину
│   ├── cart.py            # Корзина: просмотр, удаление, покупка всех позиций
│   ├── reviews.py         # Отзывы: просмотр + FSM-форма (рейтинг + текст)
│   ├── profile.py         # Личный кабинет + повтор покупки
│   ├── balance.py         # Пополнение (Stars)
│   ├── support.py         # Тикет-система + FAQ
│   ├── account_actions.py # Данные аккаунта + код + сброс сессий
│   ├── admin.py           # Админ-панель + обработка тикетов
│   └── ...
├── middlewares/
│   └── antifraud.py       # Rate limiting
└── migrations/
    └── migrate.py
```

## ✅ Чеклист перед запуском

### 1. Инфраструктура
- [ ] VPS: 2 CPU, 4 GB RAM, 20 GB SSD, Ubuntu 22.04+
- [ ] Домен + CloudFlare (проксирование, SSL)
- [ ] SSL: `sudo certbot --nginx -d your-domain.com`
- [ ] Firewall: `ufw allow 22,80,443 && ufw enable`
- [ ] Swap: 2 GB (уже в setup.sh)

### 2. Безопасность
- [ ] `.env`: скопировать `.env.example` → `.env`, заполнить реальными токенами
- [ ] `WEBHOOK_SECRET`: `openssl rand -hex 32` — обязательно!
- [ ] PostgreSQL: сменить пароль `shop:shop` на сгенерированный
- [ ] SSH: отключить root, отключить пароли, только ключи
- [ ] Fail2ban: `systemctl status fail2ban`
- [ ] Права: `chmod 600 .env`, бот работает от non-root пользователя

### 3. Проверки
- [ ] `python test_lzt.py` — должен показать баланс и аккаунты
- [ ] `python test_purchase.py` — прогон полного цикла
- [ ] Бот отвечает на `/start`
- [ ] ADMIN_CHAT_ID — группа супергруппа, бот админ

### 4. Мониторинг и обслуживание
- [ ] Sentry DSN (опционально, если доступен из вашего региона)
- [ ] UptimeRobot на `https://your-domain.com/health`
- [ ] Cron бэкапы: `0 3 * * * /opt/shop/backup.sh`
- [ ] Cron очистка логов: `0 4 * * * cd /opt/shop && python cleanup_logs.py`
- [ ] Systemd unit для автозапуска бота

### 5. CI/CD (опционально)
- [ ] Добавить в GitHub Secrets: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`
- [ ] Пуш в `main` → авто-деплой на VPS

## 🛡 Безопасность

- Атомарные транзакции PostgreSQL (`FOR UPDATE`) — исключено двойное списание
- Redis-based `purchases_paused` — потокобезопасная пауза продаж
- Rate limiting — 1 запрос/сек, 30/мин на пользователя
- Webhook secret — проверка подписи входящих запросов
- nginx rate limit + CloudFlare — защита от DDoS
- Backup bot tokens — fallback при бане основного

## 🚨 Ожидаемые риски

| Риск | Защита |
|------|--------|
| Бан бота | Автопереключение на backup token |
| Недостаток LZT баланса | Автопауза + алерт в админ-чат |
| Битый аккаунт | `cancel_buy()` → возврат на LZT |
| Двойное списание | Атомарные транзакции |
| DDoS | nginx + CloudFlare + antifraud middleware |
| Утечка токена | `.env` 600 + `WEBHOOK_SECRET` |

## 📞 Поддержка

По вопросам: создай тикет через бота (📞 Поддержка → 🎫 Создать тикет)
