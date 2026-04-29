import requests
import json
import time
from datetime import datetime

# ═══════════════════════════════════════════
#           إعدادات النظام
# ═══════════════════════════════════════════
ALPHA_VANTAGE_KEY = "GJYPRVS8J3"
TELEGRAM_TOKEN = "8786250525:AAGLrRaAu23YtPdnN1PEvNe-83afW2-PjJw"
TELEGRAM_CHAT_ID = "-1003919024252"

# الأسواق المراقبة
MARKETS = {
    "XAUUSD": {"name": "ذهب", "emoji": "🥇", "symbol": "XAU", "market": "forex"},
    "EURUSD": {"name": "يورو/دولار", "emoji": "💱", "symbol": "EUR", "market": "forex"},
    "GBPUSD": {"name": "جنيه/دولار", "emoji": "💷", "symbol": "GBP", "market": "forex"},
    "USOIL":  {"name": "نفط", "emoji": "🛢️", "symbol": "WTI", "market": "oil"},
}

# ═══════════════════════════════════════════
#         جلب بيانات السوق
# ═══════════════════════════════════════════
def get_forex_data(from_symbol, to_symbol="USD"):
    url = f"https://www.alphavantage.co/query"
    params = {
        "function": "FX_INTRADAY",
        "from_symbol": from_symbol,
        "to_symbol": to_symbol,
        "interval": "60min",
        "outputsize": "compact",
        "apikey": ALPHA_VANTAGE_KEY
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        series = data.get("Time Series FX (60min)", {})
        if not series:
            return None
        prices = []
        for ts, vals in list(series.items())[:24]:
            prices.append({
                "time": ts,
                "open": float(vals["1. open"]),
                "high": float(vals["2. high"]),
                "low": float(vals["3. low"]),
                "close": float(vals["4. close"]),
            })
        return prices
    except Exception as e:
        print(f"خطأ في جلب البيانات: {e}")
        return None

def get_gold_data():
    # الذهب عبر FX_DAILY
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "FX_INTRADAY",
        "from_symbol": "XAU",
        "to_symbol": "USD",
        "interval": "60min",
        "outputsize": "compact",
        "apikey": ALPHA_VANTAGE_KEY
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        series = data.get("Time Series FX (60min)", {})
        if not series:
            return None
        prices = []
        for ts, vals in list(series.items())[:24]:
            prices.append({
                "time": ts,
                "open": float(vals["1. open"]),
                "high": float(vals["2. high"]),
                "low": float(vals["3. low"]),
                "close": float(vals["4. close"]),
            })
        return prices
    except Exception as e:
        print(f"خطأ في جلب بيانات الذهب: {e}")
        return None

# ═══════════════════════════════════════════
#         حساب المؤشرات التقنية
# ═══════════════════════════════════════════
def calculate_atr(prices, period=14):
    trs = []
    for i in range(1, min(period+1, len(prices))):
        high = prices[i]["high"]
        low = prices[i]["low"]
        prev_close = prices[i-1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    return sum(trs) / len(trs) if trs else 0

def calculate_support_resistance(prices, period=20):
    highs = [p["high"] for p in prices[:period]]
    lows = [p["low"] for p in prices[:period]]
    resistance = max(highs)
    support = min(lows)
    return support, resistance

def calculate_rsi(prices, period=14):
    closes = [p["close"] for p in prices[:period+1]]
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i-1] - closes[i]  # مقلوب لأن الأحدث أولاً
        if diff > 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def determine_signal(prices):
    if not prices or len(prices) < 15:
        return None

    current_price = prices[0]["close"]
    atr = calculate_atr(prices)
    support, resistance = calculate_support_resistance(prices)
    rsi = calculate_rsi(prices)

    # تحديد الاتجاه
    ma5 = sum(p["close"] for p in prices[:5]) / 5
    ma20 = sum(p["close"] for p in prices[:20]) / 20

    if ma5 > ma20 and rsi < 70 and current_price > support:
        direction = "BUY"
    elif ma5 < ma20 and rsi > 30 and current_price < resistance:
        direction = "SELL"
    else:
        return None  # لا توجد فرصة واضحة

    # حساب نقاط الدخول
    if direction == "BUY":
        entry_low = round(current_price - atr * 0.3, 5)
        entry_high = round(current_price + atr * 0.1, 5)
        stop_loss = round(current_price - atr * 1.2, 5)
        targets = [
            round(current_price + atr * 0.8, 5),
            round(current_price + atr * 1.5, 5),
            round(current_price + atr * 2.2, 5),
        ]
    else:
        entry_low = round(current_price - atr * 0.1, 5)
        entry_high = round(current_price + atr * 0.3, 5)
        stop_loss = round(current_price + atr * 1.2, 5)
        targets = [
            round(current_price - atr * 0.8, 5),
            round(current_price - atr * 1.5, 5),
            round(current_price - atr * 2.2, 5),
        ]

    return {
        "direction": direction,
        "entry_low": entry_low,
        "entry_high": entry_high,
        "stop_loss": stop_loss,
        "targets": targets,
        "rsi": round(rsi, 1),
        "current_price": current_price,
    }

# ═══════════════════════════════════════════
#         تنسيق المنشور
# ═══════════════════════════════════════════
def format_message(market_key, signal):
    market = MARKETS[market_key]
    direction_ar = "🟢 شراء BUY" if signal["direction"] == "BUY" else "🔴 بيع SELL"
    now = datetime.now().strftime("%Y-%m-%d | %H:%M")

    msg = f"""
╔══════════════════════╗
     {market['emoji']} {market['name']} — إشارة تداول
╚══════════════════════╝

📌 الاتجاه: {direction_ar}

نقطة الدخول 📊 {signal['entry_low']} - {signal['entry_high']}
🚫 وقف الخسارة: {signal['stop_loss']}

🎯 أول هدف:  {signal['targets'][0]}
🎯 ثاني هدف: {signal['targets'][1]}
🎯 ثالث هدف: {signal['targets'][2]}
🎯 رابع هدف: مفتوح 🚀

👉⚠️ يرجى مراعاة إدارة رأس المال
❗️ الدخول لوت 0.10 لكل 1000$ رأس مال
❗️ #تنبيه: دخولك يكون 1% من رأس المال

📊 RSI: {signal['rsi']}
🕐 {now}

⚠️ هذه الصفقة لأغراض تعليمية فقط، وليست نصيحة مالية.

@smart_trader_sa_bot
"""
    return msg.strip()

# ═══════════════════════════════════════════
#         إرسال رسالة تيليغرام
# ═══════════════════════════════════════════
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        result = r.json()
        if result.get("ok"):
            print("✅ تم الإرسال بنجاح")
        else:
            print(f"❌ خطأ في الإرسال: {result}")
    except Exception as e:
        print(f"❌ خطأ: {e}")

# ═══════════════════════════════════════════
#         الحلقة الرئيسية
# ═══════════════════════════════════════════
def run():
    print("🚀 Smart Trader Bot يعمل...")
    signals_sent = 0

    market_fetchers = {
        "XAUUSD": lambda: get_gold_data(),
        "EURUSD": lambda: get_forex_data("EUR"),
        "GBPUSD": lambda: get_forex_data("GBP"),
        "USOIL":  lambda: get_forex_data("USO"),
    }

    for market_key, fetcher in market_fetchers.items():
        market = MARKETS[market_key]
        print(f"\n📊 تحليل {market['name']}...")

        prices = fetcher()
        if not prices:
            print(f"⚠️ لا توجد بيانات لـ {market['name']}")
            time.sleep(15)  # انتظر بين الطلبات
            continue

        signal = determine_signal(prices)
        if signal:
            msg = format_message(market_key, signal)
            print(msg)
            send_telegram(msg)
            signals_sent += 1
        else:
            print(f"⏳ لا توجد فرصة واضحة في {market['name']} الآن")

        time.sleep(15)  # انتظر بين كل سوق

    print(f"\n✅ انتهى التحليل — تم إرسال {signals_sent} إشارة")

if __name__ == "__main__":
    run()
