# ============================================
# ДОБАВИТЬ В database.py → в функцию init_db()
# ============================================

    # === ПОПОЛНЕНИЯ ЧЕРЕЗ КАРТУ ===
    c.execute("""
        CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            receipt_file_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)


# ============================================
# ДОБАВИТЬ В database.py → новые функции
# ============================================

def create_deposit(user_id: int, amount: float, status: str = "pending") -> int:
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO deposits (user_id, amount, status)
        VALUES (?, ?, ?)
        RETURNING id
    """, (user_id, amount, status))
    deposit_id = c.fetchone()["id"]
    conn.commit()
    conn.close()
    return deposit_id


def get_deposit(deposit_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM deposits WHERE id = ?", (deposit_id,))
    row = c.fetchone()
    conn.close()
    return row


def update_deposit_status(deposit_id: int, status: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        UPDATE deposits SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (status, deposit_id))
    conn.commit()
    conn.close()


def get_pending_deposits():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM deposits WHERE status = 'pending' ORDER BY created_at ASC")
    rows = c.fetchall()
    conn.close()
    return rows
