#!/usr/bin/env python3
"""
Очистка старых логов и тикетов.
Добавить в crontab:
0 4 * * * cd /opt/shop && python cleanup_logs.py >> /var/log/shop_cleanup.log 2>&1
"""
import os
import sqlite3
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shop.db")

DAYS_KEEP_LOGS = 30
DAYS_KEEP_CLOSED_TICKETS = 90


def cleanup():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Удаляем старые логи
    cutoff_logs = (datetime.now() - timedelta(days=DAYS_KEEP_LOGS)).isoformat()
    c.execute("DELETE FROM logs WHERE created_at < ?", (cutoff_logs,))
    deleted_logs = c.rowcount

    # Удаляем старые закрытые тикеты
    cutoff_tickets = (datetime.now() - timedelta(days=DAYS_KEEP_CLOSED_TICKETS)).isoformat()
    c.execute("DELETE FROM tickets WHERE status = 'closed' AND created_at < ?", (cutoff_tickets,))
    deleted_tickets = c.rowcount

    # Удаляем старые code_requests
    c.execute("DELETE FROM code_requests WHERE status != 'pending' AND created_at < ?", (cutoff_logs,))
    deleted_codes = c.rowcount

    conn.commit()
    conn.close()

    print(f"[{datetime.now()}] Очистка завершена:")
    print(f"  Удалено логов: {deleted_logs}")
    print(f"  Удалено тикетов: {deleted_tickets}")
    print(f"  Удалено code_requests: {deleted_codes}")


if __name__ == "__main__":
    cleanup()
