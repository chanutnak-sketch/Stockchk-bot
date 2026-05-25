"""
stock_analyzer.py — ดึงข้อมูลหุ้น US + Thai ด้วย Alpha Vantage API
"""
 
import asyncio
from datetime import datetime
import pytz
import pandas as pd
import requests
import os
 
 
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "")
 
THAI_STOCKS = {
    "PTT", "AOT", "KBANK", "SCB", "BBL", "ADVANC",
    "CPALL", "TRUE", "MINT", "BH", "TU", "IVL", "SCC", "PTTEP",
    "GULF", "RATCH", "EA", "WHA", "CPN", "MAJOR",
}
 
 
class StockAnalyzer:
 
    def _resolve_symbol(self, symbol: str) -> tuple:
        s = symbol.upper().strip()
        if s.endswith(".BK"):
            return s, True
        if s in THAI_STOCKS:
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
        # Alpha Vantage ใช้ BKK: แทน .BK
        av_symbol = symbol.replace(".BK", "")
        if is_thai:
            av_symbol = f"BKK:{av_symbol}"
 
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": av_symbol,
            "outputsize": "compact",
            "apikey": ALPHA_VANTAGE_KEY,
        }
 
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
 
        # ตรวจ error
        if "Error Message" in data:
            raise ValueError(f"ไม่พบข้อมูลสำหรับ {symbol}")
        if "Note" in data:
            raise ValueError("API limit reached — ลองใหม่อีก 1 นาที")
        if "Time Series (Daily)" not in data:
            raise ValueError(f"ไม่พบข้อมูลสำหรับ {symbol}")
 
        ts = data["Time Series (Daily)"]
        df = pd.DataFrame.from_dict(ts, orient="index")
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        close = df["4. close"].astype(float).tail(30)
 
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
