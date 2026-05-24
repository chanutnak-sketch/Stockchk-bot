"""
payment.py — สร้าง QR PromptPay และตรวจสอบสลิป
"""

import io
import re
import struct
import qrcode
from PIL import Image
from datetime import datetime, timedelta
import pytz

from database import Database
from config import Config


class PaymentManager:

    def generate_promptpay_qr(self, amount: float) -> io.BytesIO:
        """
        สร้าง QR Code PromptPay ตามมาตรฐาน EMVCo
        รองรับ Mobile Number และ National ID
        """
        payload = self._build_promptpay_payload(Config.PROMPTPAY_ID, amount)

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(payload)
        qr.make(fit=True)

        # สร้างภาพ QR สวยงาม
        img = qr.make_image(fill_color="#1a1a2e", back_color="white")

        # เพิ่มข้อความด้านล่าง
        from PIL import ImageDraw, ImageFont
        img = img.convert("RGB")
        draw = ImageDraw.Draw(img)

        # วาดกรอบสีม่วง
        w, h = img.size
        for i in range(3):
            draw.rectangle([i, i, w-i-1, h-i-1], outline="#6c63ff")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    def _build_promptpay_payload(self, promptpay_id: str, amount: float) -> str:
        """สร้าง EMVCo payload สำหรับ PromptPay"""

        def tlv(tag: str, value: str) -> str:
            return f"{tag}{len(value):02d}{value}"

        # ทำความสะอาด ID
        pid = re.sub(r"[^0-9]", "", promptpay_id)

        # ตรวจว่าเป็นเบอร์โทร (10 หลัก) หรือบัตรประชาชน (13 หลัก)
        if len(pid) == 10:
            pid = "0066" + pid[1:]  # แปลงเป็นรูปแบบ international
            merchant_id = tlv("00", "A000000677010111") + tlv("01", pid)
        else:
            merchant_id = tlv("00", "A000000677010111") + tlv("02", pid)

        merchant_info = tlv("29", merchant_id)

        amount_str = f"{amount:.2f}"
        payload_no_crc = (
            tlv("00", "01")         # Payload format indicator
            + tlv("01", "11")       # Point of initiation (static=11, dynamic=12)
            + merchant_info
            + tlv("52", "0000")     # Merchant category code
            + tlv("53", "764")      # Currency (764 = THB)
            + tlv("54", amount_str) # Amount
            + tlv("58", "TH")       # Country code
            + "6304"                # CRC placeholder
        )

        crc = self._crc16(payload_no_crc)
        return payload_no_crc + f"{crc:04X}"

    def _crc16(self, data: str) -> int:
        """คำนวณ CRC-16/CCITT-FALSE"""
        crc = 0xFFFF
        for char in data:
            crc ^= ord(char) << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ 0x1021
                else:
                    crc <<= 1
                crc &= 0xFFFF
        return crc

    async def verify_slip(self, slip_bytes: bytearray, payment_id: str, db: Database) -> dict:
        """
        ตรวจสอบสลิปด้วย OCR อย่างง่าย
        ในการใช้จริง ควรเชื่อมต่อ Slip Verify API เช่น EasySlip หรือ KBank API
        """
        payment = db.get_payment(payment_id)
        if not payment:
            return {"success": False, "reason": "ไม่พบ payment_id"}

        if payment["status"] == "success":
            return {"success": False, "reason": "ชำระแล้ว"}

        # ─── ใช้ EasySlip API (แนะนำ) ───────────────────
        # result = await self._verify_via_easyslip(slip_bytes, payment["amount"])

        # ─── ใช้ OCR พื้นฐาน (fallback) ──────────────────
        result = self._basic_ocr_check(slip_bytes, payment["amount"])

        if result:
            db.mark_payment_success(payment_id)
            db.activate_premium(payment["user_id"], payment["days"])

            tz = pytz.timezone("Asia/Bangkok")
            expire = datetime.now(tz) + timedelta(days=payment["days"])
            plan_map = {30: "1 เดือน", 60: "2 เดือน", 90: "3 เดือน"}

            return {
                "success": True,
                "plan": plan_map.get(payment["days"], f"{payment['days']} วัน"),
                "days": payment["days"],
                "expire_date": expire.strftime("%d/%m/%Y"),
            }

        return {"success": False, "reason": "ตรวจสอบสลิปไม่ผ่าน"}

    def _basic_ocr_check(self, slip_bytes: bytearray, expected_amount: int) -> bool:
        """
        OCR เบื้องต้นด้วย pytesseract
        ติดตั้ง: pip install pytesseract pillow
        และ: apt install tesseract-ocr tesseract-ocr-tha
        """
        try:
            import pytesseract
            from PIL import Image
            import io

            img = Image.open(io.BytesIO(bytes(slip_bytes)))
            text = pytesseract.image_to_string(img, lang="tha+eng")

            # ตรวจสอบจำนวนเงินในสลิป
            amount_str = str(expected_amount)
            return amount_str in text.replace(",", "").replace(" ", "")
        except Exception:
            # ถ้า OCR ล้มเหลว ให้ admin approve manual แทน
            return False

    # ─── EasySlip API (ใช้งานได้จริง) ───────────────────
    async def _verify_via_easyslip(self, slip_bytes: bytearray, expected_amount: int) -> bool:
        """
        ใช้ EasySlip API — https://easyslip.com
        สมัครได้ฟรี รองรับสลิปจากทุกธนาคารไทย
        """
        import aiohttp
        import base64

        api_key = Config.EASYSLIP_API_KEY
        if not api_key:
            return False

        b64 = base64.b64encode(bytes(slip_bytes)).decode()

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://developer.easyslip.com/api/v1/verify",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"image": b64}
            ) as resp:
                if resp.status != 200:
                    return False
                data = await resp.json()
                received = data.get("data", {}).get("amount", {}).get("amount", 0)
                return abs(received - expected_amount) < 1
