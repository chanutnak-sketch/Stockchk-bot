"""
Stockify Telegram Bot — รองรับ 2 ภาษา EN / TH
"""

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from database import Database
from stock_analyzer import StockAnalyzer
from payment import PaymentManager
from config import Config

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

db = Database()
analyzer = StockAnalyzer()
payment = PaymentManager()

# ─── ข้อความ 2 ภาษา ───────────────────────────────────
TEXTS = {
    "EN": {
        "welcome": "Hello! 👋\nType a stock symbol (e.g., TSLA, AAPL, PTT, AOT)\nand wait 2–3 seconds to see analysis 📊\n\nSupports 🇺🇸 US Stocks and 🇹🇭 Thai Stocks (.BK)\n\nTotal users: {total}",
        "choose_lang": "🌐 Choose your language:",
        "lang_set": "✅ Language set to English!",
        "fetching": "🔍 Fetching {symbol}...",
        "not_found": "❌ Symbol not found: `{symbol}`\nTry: TSLA, AAPL, PTT, AOT",
        "limit": "⚠️ Free limit reached.\nWait 6 hours or type /upgrade",
        "upgrade_btn": "⭐ Upgrade Premium",
        "momentum": "Momentum",
        "volatility": "Volatility",
        "indicators": "Indicators",
        "avg_price": "5-day Avg Price",
        "bollinger": "Bollinger (20)",
        "disclaimer": "_*For informational purposes only, not financial advice._",
        "upgrade_note": "⭐ *Upgrade Premium* to unlock AI Summary\nType /upgrade",
        "status_premium": "✅ *Status: Premium*\n📅 Expires: {date}\n🎉 Thank you!",
        "status_free": "🆓 *Status: Free*\n📊 Used today: {used}/{limit}\n⭐ Type /upgrade",
    },
    "TH": {
        "welcome": "สวัสดี! 👋\nพิมพ์ชื่อหุ้น (เช่น TSLA, AAPL, PTT, AOT)\nรอ 2–3 วินาที เพื่อดูการวิเคราะห์ 📊\n\nรองรับ 🇺🇸 หุ้น US และ 🇹🇭 หุ้นไทย (.BK)\n\nผู้ใช้ทั้งหมด: {total}",
        "choose_lang": "🌐 เลือกภาษา:",
        "lang_set": "✅ ตั้งค่าภาษาไทยแล้ว!",
        "fetching": "🔍 กำลังดึงข้อมูล {symbol}...",
        "not_found": "❌ ไม่พบข้อมูล `{symbol}`\nลองใช้: TSLA, AAPL, PTT, AOT",
        "limit": "⚠️ ถึงขีดจำกัดผู้ใช้ฟรีแล้ว\nรอ 6 ชั่วโมง หรือพิมพ์ /upgrade",
        "upgrade_btn": "⭐ อัปเกรด Premium",
        "momentum": "โมเมนตัม",
        "volatility": "ความผันผวน",
        "indicators": "ตัวชี้วัด",
        "avg_price": "ราคาเฉลี่ย 5 วัน",
        "bollinger": "Bollinger (20)",
        "disclaimer": "_*เพื่อการศึกษาเท่านั้น ไม่ใช่คำแนะนำทางการเงิน_",
        "upgrade_note": "⭐ *อัปเกรด Premium* เพื่อปลดล็อก AI Summary\nพิมพ์ /upgrade",
        "status_premium": "✅ *สถานะ: Premium*\n📅 หมดอายุ: {date}\n🎉 ขอบคุณที่สนับสนุน!",
        "status_free": "🆓 *สถานะ: ฟรี*\n📊 ใช้วันนี้: {used}/{limit}\n⭐ พิมพ์ /upgrade",
    }
}

def get_lang(context) -> str:
    return context.user_data.get("lang", "EN")

def t(key: str, context, **kwargs) -> str:
    lang = get_lang(context)
    text = TEXTS[lang].get(key, TEXTS["EN"].get(key, key))
    return text.format(**kwargs) if kwargs else text

# ─── /start ───────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username or user.first_name)

    keyboard = [[
        InlineKeyboardButton("🇺🇸 English", callback_data="lang_EN"),
        InlineKeyboardButton("🇹🇭 ภาษาไทย", callback_data="lang_TH"),
    ]]
    await update.message.reply_text(
        "🌐 Please choose your language / เลือกภาษา:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─── /language ────────────────────────────────────────
async def language_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton("🇺🇸 English", callback_data="lang_EN"),
        InlineKeyboardButton("🇹🇭 ภาษาไทย", callback_data="lang_TH"),
    ]]
    await update.message.reply_text(
        t("choose_lang", context),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─── Language callback ────────────────────────────────
async def lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = query.data.replace("lang_", "")
    context.user_data["lang"] = lang

    total = db.get_total_users()
    await query.message.reply_text(
        t("lang_set", context) + "\n\n" + t("welcome", context, total=total)
    )

# ─── /upgrade ─────────────────────────────────────────
async def upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💳 1 เดือน — 59 บาท", callback_data="pay_1m_59")],
        [InlineKeyboardButton("✨ 2 เดือน — 112 บาท (ลด 5%)", callback_data="pay_2m_112")],
        [InlineKeyboardButton("✨ 3 เดือน — 159 บาท (ลด 10%)", callback_data="pay_3m_159")],
    ]
    text = (
        "💳 *รายละเอียดการชำระเงิน*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ 1 เดือน : *59 บาท*\n"
        "✅ 2 เดือน : *112 บาท (ลด 5%)* ✨\n"
        "✅ 3 เดือน : *159 บาท (ลด 10%)* ✨\n\n"
        "กดปุ่มด้านล่างเพื่อรับ QR PromptPay 👇"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# ─── Payment callbacks ────────────────────────────────
async def payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_map = {
        "pay_1m_59":  ("1 เดือน",  59,  30),
        "pay_2m_112": ("2 เดือน", 112,  60),
        "pay_3m_159": ("3 เดือน", 159,  90),
    }
    plan_name, amount, days = plan_map[query.data]
    qr_image = payment.generate_promptpay_qr(amount)
    payment_id = db.create_pending_payment(query.from_user.id, amount, days)
    caption = (
        f"📱 *QR PromptPay — {plan_name} ({amount} บาท)*\n\n"
        f"1️⃣ สแกน QR โอนเงิน {amount} บาท\n"
        f"2️⃣ กด *ยืนยันการชำระ* ด้านล่าง\n"
        f"📌 Payment ID: `{payment_id}`"
    )
    keyboard = [[InlineKeyboardButton("✅ ยืนยัน + อัปโหลดสลิป", callback_data=f"confirm_{payment_id}")]]
    await query.message.reply_photo(photo=qr_image, caption=caption, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def confirm_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["waiting_slip"] = query.data.replace("confirm_", "")
    await query.message.reply_text("📸 กรุณาส่งรูปสลิปการโอนเงินได้เลยครับ")

async def goto_upgrade_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("💳 1 เดือน — 59 บาท", callback_data="pay_1m_59")],
        [InlineKeyboardButton("✨ 2 เดือน — 112 บาท", callback_data="pay_2m_112")],
        [InlineKeyboardButton("✨ 3 เดือน — 159 บาท", callback_data="pay_3m_159")],
    ]
    await query.message.reply_text("⭐ *เลือกแพ็คเกจ Premium*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# ─── รับสลิป ──────────────────────────────────────────
async def receive_slip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    payment_id = context.user_data.get("waiting_slip")
    if not payment_id:
        return
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    slip_bytes = await file.download_as_bytearray()
    await update.message.reply_text("⏳ กำลังตรวจสอบสลิป...")
    result = await payment.verify_slip(slip_bytes, payment_id, db)
    if result["success"]:
        context.user_data.pop("waiting_slip", None)
        await update.message.reply_text(f"🎉 *ยืนยันสำเร็จ! Premium {result['plan']}*\n✅ หมดอายุ: {result['expire_date']}", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ ตรวจสอบสลิปไม่สำเร็จ กรุณาติดต่อ @admin")

# ─── รับ Stock Symbol ─────────────────────────────────
async def handle_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    symbol_input = update.message.text.strip().upper()

    is_premium = db.is_premium(user_id)
    if not is_premium:
        usage = db.get_today_usage(user_id)
        if usage >= Config.FREE_DAILY_LIMIT:
            await update.message.reply_text(t("limit", context))
            return

    await update.message.reply_text(t("fetching", context, symbol=symbol_input))
    result = await analyzer.analyze(symbol_input)

    if result["error"]:
        await update.message.reply_text(t("not_found", context, symbol=symbol_input), parse_mode="Markdown")
        return

    db.increment_usage(user_id)
    text = format_message(result, is_premium, context)

    keyboard = []
    if not is_premium:
        keyboard = [[InlineKeyboardButton(t("upgrade_btn", context), callback_data="goto_upgrade")]]

    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)

def format_message(r: dict, is_premium: bool, context) -> str:
    flag = "🇹🇭" if r.get("is_thai") else "🇺🇸"
    currency = "฿" if r.get("is_thai") else "$"
    momentum_emoji = "📈" if r["momentum"] in ["Uptrend", "ขาขึ้น"] else "📉" if r["momentum"] in ["Downtrend", "ขาลง"] else "➡️"
    rsi_emoji = "🟢" if r["rsi_signal"] == "Oversold" else "🔴" if r["rsi_signal"] == "Overbought" else "⚪"
    macd_emoji = "🟢" if r["macd_signal"] == "Bullish" else "🔴"
    vol_emoji = "🔴" if r["volatility"] == "High" else "🟡" if r["volatility"] == "Medium" else "🟢"

    lang = get_lang(context)
    momentum_val = {"Uptrend": "ขาขึ้น", "Downtrend": "ขาลง", "Sideways": "ทรงตัว"}.get(r["momentum"], r["momentum"]) if lang == "TH" else r["momentum"]
    rsi_val = {"Neutral": "เป็นกลาง", "Oversold": "ขายมากเกิน", "Overbought": "ซื้อมากเกิน"}.get(r["rsi_signal"], r["rsi_signal"]) if lang == "TH" else r["rsi_signal"]
    macd_val = {"Bullish": "เป็นบวก", "Bearish": "เป็นลบ"}.get(r["macd_signal"], r["macd_signal"]) if lang == "TH" else r["macd_signal"]
    vol_val = {"High": "สูง", "Medium": "กลาง", "Low": "ต่ำ"}.get(r["volatility"], r["volatility"]) if lang == "TH" else r["volatility"]

    text = (
        f"🕐 *Updated:* {r['updated']}\n\n"
        f"📊 {flag} *{r['symbol']}*\n"
        f"{'━' * 25}\n"
        f"💡 *{t('momentum', context)}:* {momentum_val} {momentum_emoji}\n"
        f"📉 *RSI:* {r['rsi']:.1f} — {rsi_val} {rsi_emoji}\n"
        f"🎯 *MACD:* {macd_val} {macd_emoji}\n"
        f"🌊 *{t('volatility', context)}:* {vol_val} {vol_emoji}\n"
        f"{'━' * 25}\n"
        f"📌 *{t('indicators', context)}:*\n"
        f"• {t('avg_price', context)}: {r['avg_price']:.2f} {currency} 📈\n"
        f"• {t('bollinger', context)}: {r['bb_lower']:.2f} – {r['bb_upper']:.2f} 🟡\n"
    )

    if not is_premium:
        text += f"\n{'━' * 25}\n{t('disclaimer', context)}\n{t('upgrade_note', context)}"

    return text

# ─── /status ──────────────────────────────────────────
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    info = db.get_user_info(user_id)
    if info and info["is_premium"]:
        await update.message.reply_text(t("status_premium", context, date=info["premium_until"]), parse_mode="Markdown")
    else:
        await update.message.reply_text(t("status_free", context, used=db.get_today_usage(user_id), limit=Config.FREE_DAILY_LIMIT), parse_mode="Markdown")

# ─── Main ─────────────────────────────────────────────
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("ไม่พบ TELEGRAM_BOT_TOKEN ใน environment variables")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("upgrade", upgrade))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("language", language_cmd))

    app.add_handler(CallbackQueryHandler(lang_callback, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(payment_callback, pattern="^pay_"))
    app.add_handler(CallbackQueryHandler(confirm_payment_callback, pattern="^confirm_"))
    app.add_handler(CallbackQueryHandler(goto_upgrade_callback, pattern="^goto_upgrade$"))

    app.add_handler(MessageHandler(filters.PHOTO, receive_slip))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_stock))

    logger.info("🚀 Stockchk Bot เริ่มทำงานแล้ว!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
