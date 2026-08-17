"""Simple migration runner for SQLite.
Usage: python migrations/migrate.py
"""
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shop.db")
MIGRATIONS_DIR = os.path.dirname(os.path.abspath(__file__))


def run_migrations():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    files = sorted([f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql") and f != "__init__.py"])
    for fname in files:
        c.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (fname,))
        if c.fetchone():
            print(f"SKIP {fname}")
            continue
        with open(os.path.join(MIGRATIONS_DIR, fname), "r", encoding="utf-8") as f:
            sql = f.read()
        c.executescript(sql)
        c.execute("INSERT INTO schema_migrations (version) VALUES (?)", (fname,))
        conn.commit()
        print(f"APPLIED {fname}")

    conn.close()
    print("Migrations complete.")


if __name__ == "__main__":
    run_migrations()
