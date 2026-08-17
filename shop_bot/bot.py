import asyncio
import logging
import signal

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ErrorEvent
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

from config import (
    BOT_TOKEN, BACKUP_BOT_TOKENS, ADMIN_CHAT_ID, TOPIC_MONITORING,
    WEBHOOK_HOST, WEBHOOK_PORT, WEBHOOK_PATH, WEBHOOK_URL,
    MIN_LZT_BALANCE, WEBHOOK_SECRET, SENTRY_DSN
)
from redis_client import set_purchases_paused

# === Validate config before starting ===
if not BOT_TOKEN:
    logging.error("BOT_TOKEN is empty! Please copy .env.example to .env and fill it.")
    print("\n" + "="*60)
    print("ERROR: BOT_TOKEN not found!")
    print("1. Copy .env.example -> .env")
    print("2. Fill BOT_TOKEN and other fields")
    print("="*60 + "\n")
    exit(1)

from database import init_db, seed_demo_accounts
from handlers import start, buy, profile, balance, info, admin, cart, reviews, account_actions, support, referral, legal
from middlewares.antifraud import AntifraudMiddleware
from lzt_api import search_telegram_accounts, demo_search, get_lzt_balance
from redis_client import log_error_to_redis

# Init Sentry before anything else
try:
    import sentry_client
except Exception as e:
    logging.warning(f"Sentry init skipped: {e}")

logging.basicConfig(level=logging.INFO)

# === Try primary bot, fallback to backups if banned ===
_bot = None
_current_token = BOT_TOKEN

def _check_token(token: str) -> bool:
    """Check if bot token is valid."""
    try:
        loop = asyncio.new_event_loop()
        test_bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        me = loop.run_until_complete(test_bot.get_me())
        loop.run_until_complete(test_bot.session.close())
        loop.close()
        return me is not None
    except Exception as e:
        logging.warning(f"Token check failed: {token[:15]}... - {e}")
        return False

for token in [BOT_TOKEN] + BACKUP_BOT_TOKENS:
    if _check_token(token):
        _bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        _current_token = token
        logging.info(f"Bot connected with token: {token[:15]}...")
        break
    else:
        logging.warning(f"Token failed: {token[:15]}...")

if _bot is None:
    raise RuntimeError("All bot tokens are invalid or banned!")

bot = _bot

dp = Dispatcher(storage=MemoryStorage())

dp.include_router(start.router)
dp.include_router(buy.router)
dp.include_router(profile.router)
dp.include_router(balance.router)
dp.include_router(info.router)
dp.include_router(admin.router)
dp.include_router(cart.router)
dp.include_router(reviews.router)
dp.include_router(account_actions.router)
dp.include_router(support.router)
dp.include_router(referral.router)
dp.include_router(legal.router)

# Antifraud middleware
dp.message.middleware(AntifraudMiddleware())
dp.callback_query.middleware(AntifraudMiddleware())


# === Global error handler ===
@dp.error()
async def global_error_handler(event: ErrorEvent):
    exception = event.exception
    if exception:
        error_text = f"Bot Error\n\n{str(exception)[:800]}"
        logging.exception("Unhandled exception", exc_info=exception)
        try:
            log_error_to_redis(str(exception))
        except Exception:
            pass
        if ADMIN_CHAT_ID:
            try:
                await bot.send_message(ADMIN_CHAT_ID, error_text, parse_mode="HTML")
            except Exception:
                pass
        if SENTRY_DSN:
            try:
                import sentry_sdk
                sentry_sdk.capture_exception(exception)
            except Exception:
                pass
    return True


async def monitor_lzt_deals():
    await asyncio.sleep(30)
    countries = [
        ("US", "США", "🇺🇸"), ("KZ", "Казахстан", "🇰🇿"), ("IN", "Индия", "🇮🇳"),
        ("ID", "Индонезия", "🇮🇩"), ("PH", "Филиппины", "🇵🇭"), ("VN", "Вьетнам", "🇻🇳"),
        ("BR", "Бразилия", "🇧🇷"), ("AR", "Аргентина", "🇦🇷"), ("TR", "Турция", "🇹🇷"),
        ("RO", "Румыния", "🇷🇴"), ("PL", "Польша", "🇵🇱"), ("DE", "Германия", "🇩🇪"),
    ]
    while True:
        try:
            if not ADMIN_CHAT_ID:
                await asyncio.sleep(600)
                continue
            if __import__("random").random() < 0.25:
                country = __import__("random").choice(countries)
                code, name, flag = country
                account_type = __import__("random").choice(["samoreg", "autoreg"])
                type_label = "саморег" if account_type == "samoreg" else "авторег"
                items = await search_telegram_accounts(country=code)
                if not items:
                    items = demo_search(code, account_type)
                if items:
                    item = items[0]
                    price_raw = item.get("price") or item.get("price_value") or 0
                    try:
                        price = float(price_raw)
                    except (ValueError, TypeError):
                        price = 0
                    if not (5 <= price <= 300):
                        logging.info(f"Monitor: skip {code} {account_type}, price {price} out of range")
                        await asyncio.sleep(600)
                        continue
                    if price < 25:
                        sell_price = round(price * 2, 2)
                        profit = round(sell_price - price, 2)
                        kb = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="Закупить", callback_data=f"admin_buy_deal:{code}:{account_type}:{int(price)}")],
                            [InlineKeyboardButton(text="Пропустить", callback_data="admin_skip_deal")],
                        ])
                        kwargs = {"reply_markup": kb}
                        if TOPIC_MONITORING:
                            kwargs["message_thread_id"] = TOPIC_MONITORING
                        await bot.send_message(
                            ADMIN_CHAT_ID,
                            f"ВЫГОДНОЕ ПРЕДЛОЖЕНИЕ НА LZT!\n\n"
                            f"Страна: {flag} {name}\n"
                            f"Тип: {type_label}\n"
                            f"Цена продажи: ~{int(sell_price)}₽\n"
                            f"Потенциальная прибыль: {int(profit)}₽/шт\n\n"
                            f"Рекомендуется закупить заранее!",
                            **kwargs
                        )
        except Exception as e:
            logging.error(f"Monitor error: {e}")
        await asyncio.sleep(600)


async def monitor_lzt_balance():
    await asyncio.sleep(60)
    while True:
        try:
            result = await get_lzt_balance()
            lzt_balance = 0.0
            if isinstance(result, dict) and "balance" in result:
                try:
                    lzt_balance = float(result["balance"])
                except (ValueError, TypeError):
                    lzt_balance = 0.0
            if lzt_balance < MIN_LZT_BALANCE:
                if not __import__('redis_client').is_purchases_paused():
                    set_purchases_paused(True)
                    logging.warning(f"LZT balance low: {lzt_balance}. Purchases paused.")
                    if ADMIN_CHAT_ID:
                        await bot.send_message(
                            ADMIN_CHAT_ID,
                            f"Баланс LZT закончился!\n\n"
                            f"Текущий баланс: {lzt_balance} ₽\n"
                            f"Минимум для работы: {MIN_LZT_BALANCE} ₽\n\n"
                            f"Продажи автоматически приостановлены.\n"
                            f"Пополните баланс LZT для возобновления работы.",
                            parse_mode="HTML"
                        )
            else:
                if __import__('redis_client').is_purchases_paused():
                    set_purchases_paused(False)
                    logging.info(f"LZT balance restored: {lzt_balance}. Purchases resumed.")
                    if ADMIN_CHAT_ID:
                        await bot.send_message(
                            ADMIN_CHAT_ID,
                            f"Баланс LZT восстановлен\n\n"
                            f"Текущий баланс: {lzt_balance} ₽\n"
                            f"Продажи возобновлены.",
                            parse_mode="HTML"
                        )
        except Exception as e:
            logging.error(f"Balance monitor error: {e}")
        await asyncio.sleep(300)


async def on_startup():
    init_db()
    logging.info("Bot started!")
    if WEBHOOK_URL:
        await bot.set_webhook(WEBHOOK_URL)
        logging.info(f"Webhook set: {WEBHOOK_URL}")


async def on_shutdown():
    await bot.delete_webhook()
    logging.info("Webhook deleted")


dp.startup.register(on_startup)
dp.shutdown.register(on_shutdown)


# === Graceful shutdown ===
shutdown_event = asyncio.Event()


def signal_handler(sig):
    logging.info(f"Received signal {sig}, shutting down gracefully...")
    shutdown_event.set()


# === Health check ===
async def health_handler(request):
    from redis_client import is_purchases_paused
    return web.json_response({
        "status": "ok",
        "purchases_paused": is_purchases_paused(),
        "token": _current_token[:10] + "..."
    })


# === Webhook security middleware ===
@web.middleware
async def webhook_security(request, handler):
    if WEBHOOK_SECRET and request.path == WEBHOOK_PATH:
        header_secret = request.headers.get("X-Webhook-Secret", "")
        if header_secret != WEBHOOK_SECRET:
            return web.Response(status=403, text="Forbidden")
    return await handler(request)


async def main():
    asyncio.create_task(monitor_lzt_deals())
    asyncio.create_task(monitor_lzt_balance())

    if WEBHOOK_URL:
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
        app = web.Application(middlewares=[webhook_security])
        app.router.add_get("/health", health_handler)
        webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
        webhook_handler.register(app, path=WEBHOOK_PATH)
        setup_application(app, dp, bot=bot)

        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, WEBHOOK_HOST, WEBHOOK_PORT)
        await site.start()
        logging.info(f"Webhook server started on {WEBHOOK_HOST}:{WEBHOOK_PORT}")

        await shutdown_event.wait()
        await runner.cleanup()
    else:
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
