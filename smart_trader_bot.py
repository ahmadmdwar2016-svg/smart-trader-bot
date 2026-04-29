import requests
import time
from datetime import datetime

# ═══════════════════════════════════════════
#           إعدادات النظام
# ═══════════════════════════════════════════
TWELVE_DATA_KEY  = "a3ebbcf50208480695b30ae9d9b16f9e"
TELEGRAM_TOKEN   = "8786250525:AAGLrRaAu23YtPdnN1PEvNe-83afW2-PjJw"
TELEGRAM_CHAT_ID = "-1003919024252"

# الذهب والنفط = خانتين | الفوركس = 5 خانات
MARKETS = {
    "XAU/USD": {"name": "ذهب",        "emoji": "🥇", "decimals": 2},
    "XTI/USD": {"name": "نفط",         "emoji": "🛢️", "decimals": 2},
    "EUR/USD": {"name": "يورو/دولار",  "emoji": "💱", "decimals": 5},
    "GBP/USD": {"name": "جنيه/دولار", "emoji": "💷", "decimals": 5},
}

# ═══════════════════════════════════════════
#         جلب البيانات من Twelve Data
# ═══════════════════════════════════════════
def get_prices(symbol):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol":     symbol,
        "interval":   "1h",
        "outputsize": 30,
        "apikey":     TWELVE_DATA_KEY,
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if data.get("status") == "error":
            print(f"⚠️ خطأ API لـ {symbol}: {data.get('message')}")
            return None
        values = data.get("values", [])
        if not values:
            return None
        return [{"open": float(v["open"]), "high": float(v["high"]),
                 "low": float(v["low"]), "close": float(v["close"])} for v in values]
    except Exception as e:
        print(f"❌ خطأ في جلب {symbol}: {e}")
        return None

# ═══════════════════════════════════════════
#         حساب المؤشرات التقنية
# ═══════════════════════════════════════════
def calculate_atr(prices, period=14):
    trs = []
    for i in range(1, min(period + 1, len(prices))):
        h, l, pc = prices[i]["high"], prices[i]["low"], prices[i-1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / len(trs) if trs else 0

def calculate_rsi(prices, period=14):
    closes = [p["close"] for p in prices[:period + 1]]
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i-1] - closes[i]
        gains.append(abs(diff) if diff > 0 else 0)
        losses.append(abs(diff) if diff < 0 else 0)
    ag = sum(gains) / period if gains else 0
    al = sum(losses) / period if losses else 0
    return 100 if al == 0 else round(100 - (100 / (1 + ag / al)), 1)

def determine_signal(prices, decimals):
    if not prices or len(prices) < 20:
        return None
    cp   = prices[0]["close"]
    atr  = calculate_atr(prices)
    rsi  = calculate_rsi(prices)
    ma5  = sum(p["close"] for p in prices[:5])  / 5
    ma20 = sum(p["close"] for p in prices[:20]) / 20

    if ma5 > ma20 and rsi < 68:
        direction = "BUY"
    elif ma5 < ma20 and rsi > 32:
        direction = "SELL"
    else:
        return None

    d = decimals
    mul = [0.8, 1.5, 2.2]
    if direction == "BUY":
        entry_low, entry_high = round(cp - atr*0.3, d), round(cp + atr*0.1, d)
        stop_loss = round(cp - atr*1.2, d)
        targets   = [round(cp + atr*m, d) for m in mul]
    else:
        entry_low, entry_high = round(cp - atr*0.1, d), round(cp + atr*0.3, d)
        stop_loss = round(cp + atr*1.2, d)
        targets   = [round(cp - atr*m, d) for m in mul]

    return {"direction": direction, "entry_low": entry_low,
            "entry_high": entry_high, "stop_loss": stop_loss,
            "targets": targets, "rsi": rsi}

# ═══════════════════════════════════════════
#         تنسيق المنشور
# ═══════════════════════════════════════════
def format_message(symbol, signal):
    m = MARKETS[symbol]
    dir_ar = "🟢 شراء  BUY" if signal["direction"] == "BUY" else "🔴 بيع  SELL"
    now = datetime.now().strftime("%Y-%m-%d | %H:%M")
    return f"""╔══════════════════════╗
   {m['emoji']} {m['name']} — إشارة تداول
╚══════════════════════╝

📌 الاتجاه: {dir_ar}

نقطة الدخول 📊 {signal['entry_low']} - {signal['entry_high']}
🚫 وقف الخسارة: {signal['stop_loss']}

🎯 أول هدف:  {signal['targets'][0]}
🎯 ثاني هدف: {signal['targets'][1]}
🎯 ثالث هدف: {signal['targets'][2]}
🎯 رابع هدف: مفتوح 🚀

👉⚠️ يرجى مراعاة إدارة رأس المال
❗️الدخول لوت 0.10 لكل 1000$ رأس مال
❗️ #تنبيه : دخولك يكون 1% من رأس المال

📊 RSI: {signal['rsi']}
🕐 {now}

⚠️ هذه الصفقة لأغراض تعليمية فقط، وليست نصيحة مالية."""

# ═══════════════════════════════════════════
#         إرسال رسالة تيليغرام
# ═══════════════════════════════════════════
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10)
        print("✅ تم الإرسال" if r.json().get("ok") else f"❌ خطأ: {r.json()}")
    except Exception as e:
        print(f"❌ خطأ: {e}")

# ═══════════════════════════════════════════
#         الحلقة الرئيسية — كل 4 ساعات
# ═══════════════════════════════════════════
def run():
    while True:
        print(f"\n🚀 جلسة تحليل جديدة — {datetime.now().strftime('%H:%M')}")
        sent = 0
        for symbol, info in MARKETS.items():
            print(f"\n📊 تحليل {info['name']}...")
            prices = get_prices(symbol)
            if not prices:
                print(f"⚠️ لا توجد بيانات لـ {info['name']}")
                time.sleep(20)
                continue
            signal = determine_signal(prices, info["decimals"])
            if signal:
                send_telegram(format_message(symbol, signal))
                sent += 1
            else:
                print(f"⏳ لا توجد فرصة واضحة في {info['name']} الآن")
            time.sleep(20)
        print(f"\n✅ انتهى التحليل — تم إرسال {sent} إشارة")
        print("⏰ الانتظار 4 ساعات...")
        time.sleep(4 * 60 * 60)

if __name__ == "__main__":
    run()
