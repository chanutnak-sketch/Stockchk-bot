"""
stock_analyzer.py — ดึงข้อมูลและวิเคราะห์หุ้น US + Thai
"""

import asyncio
from datetime import datetime, timezone, timedelta
import pytz
import pandas as pd
import numpy as np
import yfinance as yf


class StockAnalyzer:

    THAI_SUFFIXES = [".BK"]
    THAI_STOCKS_NO_SUFFIX = {
        # หุ้นไทยที่ user พิมพ์แค่ชื่อย่อ เช่น PTT → PTT.BK
        "PTT", "AOT", "KBANK", "SCB", "BBL", "ADVANC", "DTAC",
        "CPALL", "TRUE", "MINT", "BH", "TU", "IVL", "SCC", "PTTEP",
        "GULF", "RATCH", "BCPG", "EA", "WHA", "CPN", "MAJOR",
    }

    def _resolve_symbol(self, symbol: str) -> tuple[str, bool]:
        """คืนค่า (yfinance_symbol, is_thai)"""
        # ถ้าลงท้าย .BK แล้ว
        if symbol.endswith(".BK"):
            return symbol, True
        # ถ้าอยู่ใน whitelist หุ้นไทย
        if symbol in self.THAI_STOCKS_NO_SUFFIX:
            return f"{symbol}.BK", True
        return symbol, False

    async def analyze(self, symbol_input: str) -> dict:
        symbol, is_thai = self._resolve_symbol(symbol_input)

        try:
            data = await asyncio.to_thread(self._fetch_and_calc, symbol, is_thai)
            return data
        except Exception as e:
            return {"error": str(e)}

    def _fetch_and_calc(self, symbol: str, is_thai: bool) -> dict:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="30d")

        if hist.empty or len(hist) < 5:
            raise ValueError(f"ไม่พบข้อมูลสำหรับ {symbol}")

        close = hist["Close"]

        # ─── Indicators ───────────────────────────────────
        avg_5 = close.tail(5).mean()

        # RSI (14)
        rsi = self._calc_rsi(close, 14)
        rsi_val = rsi.iloc[-1]
        if rsi_val < 30:
            rsi_signal = "Oversold"
        elif rsi_val > 70:
            rsi_signal = "Overbought"
        else:
            rsi_signal = "Neutral"

        # MACD (12, 26, 9)
        macd_line, signal_line = self._calc_macd(close)
        macd_signal = "Bullish" if macd_line.iloc[-1] > signal_line.iloc[-1] else "Bearish"

        # Bollinger Bands (20)
        bb_mid = close.rolling(20).mean()
        bb_std = close.rolling(20).std()
        bb_upper = (bb_mid + 2 * bb_std).iloc[-1]
        bb_lower = (bb_mid - 2 * bb_std).iloc[-1]

        # Momentum
        price_now = close.iloc[-1]
        price_5d_ago = close.iloc[-5]
        change_pct = (price_now - price_5d_ago) / price_5d_ago * 100
        if change_pct > 2:
            momentum = "Uptrend"
        elif change_pct < -2:
            momentum = "Downtrend"
        else:
            momentum = "Sideways"

        # Volatility (std ของ daily return 10 วัน)
        daily_ret = close.pct_change().tail(10).std() * 100
        if daily_ret > 3:
            volatility = "High"
        elif daily_ret > 1.5:
            volatility = "Medium"
        else:
            volatility = "Low"

        # เวลา GMT+7
        tz = pytz.timezone("Asia/Bangkok")
        updated = datetime.now(tz).strftime("%Y-%m-%d %H:%M")

        return {
            "error": None,
            "symbol": symbol.replace(".BK", "") if is_thai else symbol,
            "is_thai": is_thai,
            "updated": f"{updated} (GMT+7)",
            "momentum": momentum,
            "rsi": rsi_val,
            "rsi_signal": rsi_signal,
            "macd_signal": macd_signal,
            "volatility": volatility,
            "avg_price": avg_5,
            "bb_upper": bb_upper,
            "bb_lower": bb_lower,
            "current_price": price_now,
            "change_pct": change_pct,
        }

    # ─── Helper: RSI ──────────────────────────────────────
    def _calc_rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    # ─── Helper: MACD ─────────────────────────────────────
    def _calc_macd(self, series: pd.Series):
        ema12 = series.ewm(span=12, adjust=False).mean()
        ema26 = series.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        return macd_line, signal_line
