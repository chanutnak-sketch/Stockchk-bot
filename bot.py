"""
Stockify Telegram Bot - Main Bot File
รองรับ US และ Thai Stocks + ระบบ Premium ด้วย PromptPay QR
"""

import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from database import Database
from stock_analyzer import StockAnalyzer
from payment import PaymentManager
from config import Config

# ตั้งค่า logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db = Database()
analyzer = StockAnalyzer()
payment = PaymentManager()


# ─────────────────────────────────────────────
# /start
# ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username or user.first_name)
    total_users = db.get_total_users()

    text = (
        f"Hello! 👋\n"
        f"Type a stock symbol (e.g., TSLA, AAPL, PTT, AOT)\n"
        f"and wait 2–3 seconds to see its 3-5 day Sharpe trend 📊\n\n"
        f"รองรับทั้ง 🇺🇸 US Stocks และ 🇹🇭 Thai Stocks (.BK)\n\n"
        f"Total users: {total_users}"
    )
    await update.message.reply_text(text)


# ─────────────────────────────────────────────
# /upgrade — แสดงราคา + ปุ่ม QR
# ─────────────────────────────────────────────
async def upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💳 1 เดือน — 59 บาท", callback_data="pay_1m_59")],
        [InlineKeyboardButton("✨ 2 เดือน — 112 บาท (ลด 5%)", callback_data="pay_2m_112")],
        [InlineKeyboardButton("✨ 3 เดือน — 159 บาท (ลด 10%)", callback_data="pay_3m_159")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "💳 *รายละเอียดการชำระเงิน*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🔥 *โปรโมชั่นพิเศษ*\n\n"
        "✅ 1 เดือน : *59 บาท*\n"
        "✅ 2 เดือน : *112 บาท (ลด 5%)* ✨\n"
        "✅ 3 เดือน : *159 บาท (ลด 10%)* ✨\n\n"
        "กดปุ่มด้านล่างเพื่อรับ QR PromptPay ได้เลยครับ 👇"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)


# ─────────────────────────────────────────────
# Callback — สร้าง QR PromptPay
# ─────────────────────────────────────────────
async def payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data  # e.g. "pay_1m_59"

    plan_map = {
        "pay_1m_59":  ("1 เดือน",  59,  30),
        "pay_2m_112": ("2 เดือน", 112,  60),
        "pay_3m_159": ("3 เดือน", 159,  90),
    }

    plan_name, amount, days = plan_map[data]

    # สร้าง QR PromptPay
    qr_image = payment.generate_promptpay_qr(amount)

    # บันทึก pending payment ลง DB
    payment_id = db.create_pending_payment(user_id, amount, days)

    caption = (
        f"📱 *QR PromptPay — {plan_name} ({amount} บาท)*\n\n"
        f"1️⃣ สแกน QR โอนเงิน {amount} บาท\n"
        f"2️⃣ กด *ยืนยันการชำระ* ด้านล่าง\n"
        f"3️⃣ อัปโหลดสลิป เพื่อให้ระบบตรวจสอบ\n\n"
        f"⚠️ ระบบตรวจสอบสลิปอัตโนมัติภายใน *5 นาที*\n"
        f"📌 Payment ID: `{payment_id}`"
    )

    keyboard = [[InlineKeyboardButton("✅ ยืนยันการชำระ + อัปโหลดสลิป", callback_data=f"confirm_{payment_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.reply_photo(
        photo=qr_image,
        caption=caption,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


# ─────────────────────────────────────────────
# Callback — รอสลิปจาก user
# ─────────────────────────────────────────────
async def confirm_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    payment_id = query.data.replace("confirm_", "")
    user_id = query.from_user.id

    # เก็บ state รอรับสลิป
    context.user_data["waiting_slip"] = payment_id

    await query.message.reply_text(
        "📸 กรุณาส่งรูปสลิปการโอนเงินได้เลยครับ\n"
        "(ส่งเป็นรูปภาพในช่องนี้)"
    )


# ─────────────────────────────────────────────
# รับสลิปจาก user
# ─────────────────────────────────────────────
async def receive_slip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    payment_id = context.user_data.get("waiting_slip")

    if not payment_id:
        return  # ไม่ได้รอสลิป

    # ดาวน์โหลดสลิป
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    slip_bytes = await file.download_as_bytearray()

    await update.message.reply_text("⏳ กำลังตรวจสอบสลิป...")

    # ตรวจสอบสลิป (OCR / manual)
    result = await payment.verify_slip(slip_bytes, payment_id, db)

    if result["success"]:
        days = result["days"]
        db.activate_premium(user_id, days)
        context.user_data.pop("waiting_slip", None)

        await update.message.reply_text(
            f"🎉 *ยืนยันสำเร็จ! คุณได้รับ Premium {result['plan']}*\n\n"
            f"✅ Premium หมดอายุ: {result['expire_date']}\n"
            f"🌟 ขอบคุณที่สนับสนุนนะครับ!",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "❌ ตรวจสอบสลิปไม่สำเร็จ\n"
            "กรุณาส่งสลิปอีกครั้ง หรือติดต่อ @admin"
        )


# ─────────────────────────────────────────────
# รับ Stock Symbol
# ─────────────────────────────────────────────
async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    symbol_input = update.message.text.strip().upper()

    # ตรวจ free limit
    is_premium = db.is_premium(user_id)
    if not is_premium:
        usage = db.get_today_usage(user_id)
        if usage >= Config.FREE_DAILY_LIMIT:
            await update.message.reply_text(
                "⚠️ ถึงขีดจำกัดผู้ใช้ฟรีแล้ว\n"
                "โปรดรอ 6 ชั่วโมง หรืออัปเกรด Premium\n\n"
                "พิมพ์ /upgrade เพื่อใช้งานต่อได้ทันที"
            )
            return

    await update.message.reply_text(f"🔍 กำลังดึงข้อมูล {symbol_input}...")

    # ดึงข้อมูล + วิเคราะห์
    result = await analyzer.analyze(symbol_input)

    if result["error"]:
        await update.message.reply_text(
            f"❌ ไม่พบข้อมูล `{symbol_input}`\n"
            f"ลองใช้: TSLA, AAPL, PTT.BK, AOT.BK",
            parse_mode="Markdown"
        )
        return

    db.increment_usage(user_id)

    # สร้างข้อความ
    text = format_stock_message(result, is_premium)

    if is_premium and result.get("ai_summary"):
        text += f"\n\n🤖 *AI Summary:*\n{result['ai_summary']}"

    keyboard = []
    if not is_premium:
        keyboard = [[InlineKeyboardButton("⭐ Upgrade Premium", callback_data="goto_upgrade")]]

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)


def format_stock_message(r: dict, is_premium: bool) -> str:
    flag = "🇹🇭" if r.get("is_thai") else "🇺🇸"
    momentum_emoji = "📈" if r["momentum"] == "Uptrend" else "📉" if r["momentum"] == "Downtrend" else "➡️"
    rsi_emoji = "🟢" if r["rsi_signal"] == "Oversold" else "🔴" if r["rsi_signal"] == "Overbought" else "⚪"
    macd_emoji = "🟢" if r["macd_signal"] == "Bullish" else "🔴"
    vol_emoji = "🔴" if r["volatility"] == "High" else "🟡" if r["volatility"] == "Medium" else "🟢"

    text = (
        f"🕐 *Updated:* {r['updated']}\n\n"
        f"📊 *{flag} {r['symbol']}*\n"
        f"{'━' * 30}\n"
        f"💡 *Momentum:* {r['momentum']} {momentum_emoji}\n"
        f"📉 *RSI:* {r['rsi']:.1f} — {r['rsi_signal']} {rsi_emoji}\n"
        f"🎯 *MACD:* {r['macd_signal']} {macd_emoji}\n"
        f"🌊 *Volatility:* {r['volatility']} {vol_emoji}\n"
        f"{'━' * 30}\n"
        f"📌 *Indicators:*\n"
        f"• 5-day Avg Price: {r['avg_price']:.2f} {'฿' if r.get('is_thai') else '$'} 📈\n"
        f"• Bollinger (20): {r['bb_lower']:.2f} – {r['bb_upper']:.2f} 🟡\n"
    )

    if not is_premium:
        text += (
            f"\n{'━' * 30}\n"
            f"_*For informational purposes only, not financial advice._\n"
            f"⭐ *Upgrade Premium* เพื่อปลดล็อก AI Summary\n"
            f"พิมพ์ /upgrade"
        )

    return text


# ─────────────────────────────────────────────
# Goto upgrade callback
# ─────────────────────────────────────────────
async def goto_upgrade_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # ส่งข้อมูล upgrade ใหม่
    keyboard = [
        [InlineKeyboardButton("💳 1 เดือน — 59 บาท", callback_data="pay_1m_59")],
        [InlineKeyboardButton("✨ 2 เดือน — 112 บาท (ลด 5%)", callback_data="pay_2m_112")],
        [InlineKeyboardButton("✨ 3 เดือน — 159 บาท (ลด 10%)", callback_data="pay_3m_159")],
    ]
    await query.message.reply_text(
        "⭐ *เลือกแพ็คเกจ Premium*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ─────────────────────────────────────────────
# /status — เช็คสถานะ premium
# ─────────────────────────────────────────────
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    info = db.get_user_info(user_id)

    if info and info["is_premium"]:
        text = (
            f"✅ *สถานะ: Premium*\n"
            f"📅 หมดอายุ: {info['premium_until']}\n"
            f"🎉 ขอบคุณที่สนับสนุน!"
        )
    else:
        text = (
            f"🆓 *สถานะ: Free*\n"
            f"📊 ใช้ไปวันนี้: {db.get_today_usage(user_id)}/{Config.FREE_DAILY_LIMIT} ครั้ง\n"
            f"⭐ พิมพ์ /upgrade เพื่ออัปเกรด"
        )
    await update.message.reply_text(text, parse_mode="Markdown")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("ไม่พบ TELEGRAM_BOT_TOKEN ใน environment variables")

    app = Application.builder().token(token).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("upgrade", upgrade))
    app.add_handler(CommandHandler("status", status))

    # Callbacks
    app.add_handler(CallbackQueryHandler(payment_callback, pattern="^pay_"))
    app.add_handler(CallbackQueryHandler(confirm_payment_callback, pattern="^confirm_"))
    app.add_handler(CallbackQueryHandler(goto_upgrade_callback, pattern="^goto_upgrade$"))

    # รับสลิป (รูปภาพ)
    app.add_handler(MessageHandler(filters.PHOTO, receive_slip))

    # รับ stock symbol (ข้อความทั่วไป)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_stock))

    logger.info("🚀 Stockify Bot เริ่มทำงานแล้ว!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
