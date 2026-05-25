"""
stock_analyzer.py — ดึงข้อมูลและวิเคราะห์หุ้น US + Thai
แก้ปัญหา Yahoo Finance block โดยใช้ requests session + headers
"""
 
import asyncio
from datetime import datetime
import pytz
import pandas as pd
import requests
import yfinance as yf
 
 
def _get_session():
    """สร้าง session ที่จำลองเป็น browser เพื่อหลีกเลี่ยงการ block"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    })
    return session
 
 
class StockAnalyzer:
 
    THAI_STOCKS = {
        "PTT", "AOT", "KBANK", "SCB", "BBL", "ADVANC", "DTAC",
        "CPALL", "TRUE", "MINT", "BH", "TU", "IVL", "SCC", "PTTEP",
        "GULF", "RATCH", "BCPG", "EA", "WHA", "CPN", "MAJOR",
    }
 
    def _resolve_symbol(self, symbol: str) -> tuple:
        s = symbol.upper().strip()
        if s.endswith(".BK"):
            return s, True
        if s in self.THAI_STOCKS:
            return f"{s}.BK", True
        return s, False
 
    async def analyze(self, symbol_input: str) -> dict:
        symbol, is_thai = self._resolve_symbol(symbol_input)
        try:
            data = await asyncio.to_thread(self._fetch_and_calc, symbol, is_thai)
            return data
        except Exception as e:
            return {"error": str(e)}
 
    def _fetch_and_calc(self, symbol: str, is_thai: bool) -> dict:
        session = _get_session()
        ticker = yf.Ticker(symbol, session=session)
        hist = ticker.history(period="30d", auto_adjust=True)
 
        if hist is None or hist.empty or len(hist) < 5:
            # ลอง period สั้นกว่า
            hist = ticker.history(period="5d", auto_adjust=True)
            if hist is None or hist.empty:
                raise ValueError(f"ไม่พบข้อมูลสำหรับ {symbol}")
 
        close = hist["Close"].dropna()
        if len(close) < 3:
            raise ValueError(f"ข้อมูลไม่เพียงพอสำหรับ {symbol}")
 
        avg_5 = float(close.tail(5).mean())
        price_now = float(close.iloc[-1])
        price_5d = float(close.iloc[max(-5, -len(close))])
        change_pct = (price_now - price_5d) / price_5d * 100
 
        # Momentum
        if change_pct > 2:
            momentum = "Uptrend"
        elif change_pct < -2:
            momentum = "Downtrend"
        else:
            momentum = "Sideways"
 
        # RSI
        rsi_val = self._calc_rsi(close) if len(close) >= 14 else 50.0
        if rsi_val < 30:
            rsi_signal = "Oversold"
        elif rsi_val > 70:
            rsi_signal = "Overbought"
        else:
            rsi_signal = "Neutral"
 
        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        macd_signal = "Bullish" if float(macd.iloc[-1]) > float(signal.iloc[-1]) else "Bearish"
 
        # Bollinger Bands
        period = min(20, len(close))
        bb_mid = close.rolling(period).mean()
        bb_std = close.rolling(period).std()
        bb_upper = float((bb_mid + 2 * bb_std).iloc[-1])
        bb_lower = float((bb_mid - 2 * bb_std).iloc[-1])
 
        # Volatility
        daily_ret = float(close.pct_change().tail(10).std() * 100)
        if daily_ret > 3:
            volatility = "High"
        elif daily_ret > 1.5:
            volatility = "Medium"
        else:
            volatility = "Low"
 
        tz = pytz.timezone("Asia/Bangkok")
        updated = datetime.now(tz).strftime("%Y-%m-%d %H:%M")
        display = symbol.replace(".BK", "") if is_thai else symbol
 
        return {
            "error": None,
            "symbol": display,
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
 
    def _calc_rsi(self, series: pd.Series, period: int = 14) -> float:
        delta = series.diff().dropna()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1])
