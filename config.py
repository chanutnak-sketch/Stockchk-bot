"""
config.py — ตั้งค่าทั้งหมดของ bot
แก้ไขค่าด้านล่างก่อนรัน
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ─── Telegram ─────────────────────────────────────────
    # รับจาก @BotFather บน Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

    # ─── PromptPay ────────────────────────────────────────
    # ใส่เบอร์โทร (10 หลัก) หรือบัตรประชาชน (13 หลัก)
    PROMPTPAY_ID: str = os.getenv("PROMPTPAY_ID", "0812345678")

    # ─── EasySlip API (ตรวจสอบสลิปอัตโนมัติ) ─────────────
    # สมัครฟรีที่ https://easyslip.com
    EASYSLIP_API_KEY: str = os.getenv("EASYSLIP_API_KEY", "")

    # ─── Admin ────────────────────────────────────────────
    # user_id ของ admin (เอาไว้รับ alert และ manual approve)
    ADMIN_USER_IDS: list[int] = [
        int(x) for x in os.getenv("ADMIN_USER_IDS", "0").split(",") if x.strip()
    ]

    # ─── Free tier limits ─────────────────────────────────
    FREE_DAILY_LIMIT: int = int(os.getenv("FREE_DAILY_LIMIT", "5"))

    # ─── Database ─────────────────────────────────────────
    DB_PATH: str = os.getenv("DB_PATH", "stockify.db")
