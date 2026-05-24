"""
database.py — SQLite database สำหรับเก็บข้อมูล users, premium, payments
"""

import sqlite3
import uuid
from datetime import datetime, timedelta
import pytz


class Database:
    def __init__(self, db_path: str = "stockify.db"):
        self.db_path = db_path
        self._init_db()

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id     INTEGER PRIMARY KEY,
                    username    TEXT,
                    is_premium  INTEGER DEFAULT 0,
                    premium_until TEXT,
                    created_at  TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS usage_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER,
                    date        TEXT,
                    count       INTEGER DEFAULT 0,
                    UNIQUE(user_id, date)
                );

                CREATE TABLE IF NOT EXISTS payments (
                    payment_id  TEXT PRIMARY KEY,
                    user_id     INTEGER,
                    amount      INTEGER,
                    days        INTEGER,
                    status      TEXT DEFAULT 'pending',
                    created_at  TEXT DEFAULT (datetime('now')),
                    verified_at TEXT
                );
            """)

    # ─── Users ────────────────────────────────────────────
    def add_user(self, user_id: int, username: str):
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                (user_id, username)
            )

    def get_total_users(self) -> int:
        with self._conn() as conn:
            row = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()
            return row["c"]

    def get_user_info(self, user_id: int) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            return dict(row) if row else None

    def is_premium(self, user_id: int) -> bool:
        info = self.get_user_info(user_id)
        if not info or not info["is_premium"]:
            return False
        # ตรวจวันหมดอายุ
        tz = pytz.timezone("Asia/Bangkok")
        now_str = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
        return info["premium_until"] > now_str

    def activate_premium(self, user_id: int, days: int):
        tz = pytz.timezone("Asia/Bangkok")
        now = datetime.now(tz)
        expire = now + timedelta(days=days)
        expire_str = expire.strftime("%Y-%m-%d %H:%M:%S")
        with self._conn() as conn:
            conn.execute(
                "UPDATE users SET is_premium=1, premium_until=? WHERE user_id=?",
                (expire_str, user_id)
            )

    # ─── Usage ────────────────────────────────────────────
    def get_today_usage(self, user_id: int) -> int:
        today = datetime.now().strftime("%Y-%m-%d")
        with self._conn() as conn:
            row = conn.execute(
                "SELECT count FROM usage_log WHERE user_id=? AND date=?",
                (user_id, today)
            ).fetchone()
            return row["count"] if row else 0

    def increment_usage(self, user_id: int):
        today = datetime.now().strftime("%Y-%m-%d")
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO usage_log (user_id, date, count) VALUES (?, ?, 1)
                ON CONFLICT(user_id, date) DO UPDATE SET count = count + 1
            """, (user_id, today))

    # ─── Payments ─────────────────────────────────────────
    def create_pending_payment(self, user_id: int, amount: int, days: int) -> str:
        payment_id = str(uuid.uuid4())[:8].upper()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO payments (payment_id, user_id, amount, days) VALUES (?, ?, ?, ?)",
                (payment_id, user_id, amount, days)
            )
        return payment_id

    def get_payment(self, payment_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM payments WHERE payment_id=?", (payment_id,)
            ).fetchone()
            return dict(row) if row else None

    def mark_payment_success(self, payment_id: str):
        tz = pytz.timezone("Asia/Bangkok")
        now_str = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
        with self._conn() as conn:
            conn.execute(
                "UPDATE payments SET status='success', verified_at=? WHERE payment_id=?",
                (now_str, payment_id)
            )
