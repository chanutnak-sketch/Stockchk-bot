# 🚀 Stockify Bot — คู่มือติดตั้งฉบับสมบูรณ์

## โครงสร้างไฟล์

```
stockify_bot/
├── bot.py              ← ไฟล์หลัก
├── stock_analyzer.py   ← ดึงและวิเคราะห์หุ้น
├── database.py         ← SQLite database
├── payment.py          ← QR PromptPay + ตรวจสลิป
├── config.py           ← ตั้งค่าทั้งหมด
├── requirements.txt    ← libraries ที่ต้องใช้
├── Procfile            ← สำหรับ deploy
└── .env.example        ← template ตัวแปร
```

-----

## ขั้นตอนที่ 1 — สร้าง Telegram Bot

1. เปิด Telegram → ค้นหา **@BotFather**
1. พิมพ์ `/newbot`
1. ตั้งชื่อ bot เช่น `Stockify`
1. ตั้ง username เช่น `mystockify_bot`
1. **คัดลอก Token** ที่ได้ — จะใช้ใน `.env`

-----

## ขั้นตอนที่ 2 — หา Admin User ID

1. เปิด Telegram → ค้นหา **@userinfobot**
1. กด Start → จะเห็น **Your ID: 123456789**
1. คัดลอกตัวเลขนั้นไว้

-----

## ขั้นตอนที่ 3 — ตั้งค่า .env

```bash
cp .env.example .env
```

แก้ไข `.env`:

```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHI...   ← ใส่ token จาก BotFather
PROMPTPAY_ID=0812345678                       ← เบอร์ PromptPay ของคุณ
ADMIN_USER_IDS=123456789                      ← user ID ของคุณ
EASYSLIP_API_KEY=                            ← ใส่ถ้ามี (ดูขั้นตอนที่ 4)
```

-----

## ขั้นตอนที่ 4 — EasySlip API (ตรวจสลิปอัตโนมัติ)

1. ไปที่ <https://easyslip.com>
1. สมัครบัญชีฟรี
1. ไปที่ Dashboard → API Key → คัดลอก
1. ใส่ใน `.env` ที่ `EASYSLIP_API_KEY=`

> ถ้าไม่มี API Key ระบบจะใช้ OCR พื้นฐานแทน

-----

## ขั้นตอนที่ 5 — รันบนเครื่องตัวเอง (ทดสอบ)

### ติดตั้ง Python dependencies

```bash
pip install -r requirements.txt
```

### ติดตั้ง Tesseract OCR (สำหรับอ่านสลิป)

```bash
# Ubuntu/Debian
sudo apt install tesseract-ocr tesseract-ocr-tha

# macOS
brew install tesseract tesseract-lang
```

### รัน bot

```bash
python bot.py
```

-----

## ขั้นตอนที่ 6 — Deploy ออนไลน์ (เลือก 1 วิธี)

### ✅ วิธีที่ 1: Railway.app (แนะนำ — ฟรี $5/เดือน)

1. ไปที่ <https://railway.app> → Sign up ด้วย GitHub
1. กด **New Project** → **Deploy from GitHub repo**
1. อัปโหลด/push โค้ดขึ้น GitHub ก่อน
1. ใน Railway → **Variables** → เพิ่มค่าจาก `.env` ทั้งหมด
1. Railway จะ deploy อัตโนมัติ ✅

### ✅ วิธีที่ 2: Render.com (ฟรี แต่ sleep หลัง 15 นาที)

1. ไปที่ <https://render.com> → สร้างบัญชี
1. New → **Background Worker**
1. เชื่อม GitHub repo
1. Build Command: `pip install -r requirements.txt`
1. Start Command: `python bot.py`
1. เพิ่ม Environment Variables

### ✅ วิธีที่ 3: VPS (ควบคุมได้เต็มที่)

```bash
# SSH เข้า VPS แล้วรัน:
git clone <your_repo>
cd stockify_bot
pip install -r requirements.txt
cp .env.example .env && nano .env  # แก้ค่า

# รันตลอดเวลาด้วย screen
screen -S stockify
python bot.py
# Ctrl+A, D เพื่อ detach
```

-----

## ทดสอบ Bot

1. เปิด Telegram → ค้นหา bot ของคุณ
1. พิมพ์ `/start`
1. พิมพ์ `TSLA` หรือ `PTT` → ดูว่าได้ข้อมูลไหม
1. พิมพ์ `/upgrade` → ดู QR PromptPay
1. ทดสอบโอนเงิน + ส่งสลิป

-----

## ปัญหาที่พบบ่อย

|ปัญหา     |วิธีแก้                               |
|---------|-----------------------------------|
|Bot ไม่ตอบ|ตรวจ `TELEGRAM_BOT_TOKEN` ใน `.env`|
|หุ้นไม่เจอ  |ลองเพิ่ม `.BK` เช่น `PTT.BK`          |
|QR ไม่ถูก  |ตรวจ `PROMPTPAY_ID` ว่าถูกรูปแบบ      |
|สลิปไม่ผ่าน |เพิ่ม `EASYSLIP_API_KEY`             |

-----

## Commands ทั้งหมด

|Command           |คำอธิบาย          |
|------------------|----------------|
|`/start`          |เริ่มต้นใช้งาน      |
|`/upgrade`        |ดูแพ็คเกจ Premium |
|`/status`         |เช็คสถานะ Premium|
|`TSLA`            |ดูข้อมูลหุ้น US      |
|`PTT` หรือ `PTT.BK`|ดูข้อมูลหุ้นไทย      |

-----

## ติดต่อ / ช่วยเหลือ

หากติดปัญหาในการติดตั้ง สอบถามได้ผ่าน Claude 😊