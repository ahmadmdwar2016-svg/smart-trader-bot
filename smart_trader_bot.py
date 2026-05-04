import requests
import time
import os
from datetime import datetime, timezone, timedelta

# ═══════════════════════════════════════════
#           إعدادات النظام
# ═══════════════════════════════════════════
TWELVE_DATA_KEY  = "a3ebbcf50208480695b30ae9d9b16f9e"
TELEGRAM_TOKEN   = "8786250525:AAGLrRaAu23YtPdnN1PEvNe-83afW2-PjJw"
TELEGRAM_CHAT_ID = "-1003919024252"

MARKETS = {
    "XAU/USD": {"name": "ذهب",        "emoji": "🥇", "decimals": 2},
    "XTI/USD": {"name": "نفط",         "emoji": "🛢️", "decimals": 2},
    "EUR/USD": {"name": "يورو/دولار",  "emoji": "💱", "decimals": 5},
    "GBP/USD": {"name": "جنيه/دولار", "emoji": "💷", "decimals": 5},
}

SENT_LOG = "/tmp/sent_log.txt"

# ═══════════════════════════════════════════
#   أوقات سوق الفوركس والذهب (UTC)
#
#   السوق يفتح: الأحد 22:00 UTC
#   السوق يغلق: الجمعة 22:00 UTC
#   أول ساعتين بعد الافتتاح = 22:00-00:00 UTC الأحد
# ═══════════════════════════════════════════
def is_market_open():
    now_utc = datetime.now(timezone.utc)
    day  = now_utc.weekday()   # 0=الاثنين ... 6=الأحد
    hour = now_utc.hour
    minute = now_utc.minute

    # السبت كامل = مغلق
    if day == 5:
        print(f"📅 السبت — السوق مغلق")
        return False

    # الأحد قبل 22:00 UTC = مغلق
    if day == 6 and hour < 22:
        print(f"📅 الأحد قبل الافتتاح — السوق مغلق")
        return False

    # الأحد 22:00-23:59 UTC = أول ساعتين بعد الافتتاح — لا إرسال
    if day == 6 and hour >= 22:
        print(f"⏳ أول ساعتين من افتتاح السوق — انتظار")
        return False

    # الاثنين 00:00-00:00 UTC = ساعة ثانية من الافتتاح — لا إرسال
    if day == 0 and hour == 0:
        print(f"⏳ أول ساعتين من افتتاح السوق — انتظار")
        return False

    # الجمعة بعد 22:00 UTC = مغلق
    if day == 4 and hour >= 22:
        print(f"📅 الجمعة بعد الإغلاق — السوق مغلق")
        return False

    return True

# ═══════════════════════════════════════════
#         منع الإرسال المكرر
# ═══════════════════════════════════════════
def already_sent(symbol, hours=1):
    if not os.path.exists(SENT_LOG):
        return False
    with open(SENT_LOG, "r") as f:
        lines = f.readlines()
    now = datetime.now().timestamp()
    for line in lines:
        parts = line.strip().split("|")
        if len(parts) == 2 and parts[0] == symbol:
            if now - float(parts[1]) < hours * 60 * 60:
                return True
    return False

def mark_sent(symbol):
    lines = []
    if os.path.exists(SENT_LOG):
        with open(SENT_LOG, "r") as f:
            lines = [l for l in f.readlines() if not l.startswith(symbol)]
    lines.append(f"{symbol}|{datetime.now().timestamp()}\n")
    with open(SENT_LOG, "w") as f:
        f.writelines(lines)

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

def determine_signal(prices, symbol):
    d = MARKETS[symbol]["decimals"]
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

    if symbol == "XAU/USD":
        step = 3.0
        t1, t2, t3 = 5.0, 10.0, 15.0
        sl  = 10.0
        if direction == "BUY":
            entry_low, entry_high = round(cp - step, d), round(cp + step, d)
            stop_loss = round(cp - sl, d)
            targets   = [round(cp + t1, d), round(cp + t2, d), round(cp + t3, d)]
        else:
            entry_low, entry_high = round(cp - step, d), round(cp + step, d)
            stop_loss = round(cp + sl, d)
            targets   = [round(cp - t1, d), round(cp - t2, d), round(cp - t3, d)]
    else:
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
#   الحلقة الرئيسية
#   الذهب  = كل ساعة
#   الباقي = كل 4 ساعات
# ═══════════════════════════════════════════
def run():
    while True:
        now_str = datetime.now().strftime("%H:%M")
        print(f"\n🚀 دورة تحليل جديدة — {now_str}")

        # تحقق من أوقات السوق
        if not is_market_open():
            print("⏰ الانتظار 30 دقيقة للتحقق مجدداً...")
            time.sleep(30 * 60)
            continue

        # ── الذهب أولاً — كل ساعة ──────────────
        symbol = "XAU/USD"
        info   = MARKETS[symbol]
        print(f"\n📊 تحليل {info['name']}...")

        if already_sent(symbol, hours=1):
            print(f"⏭️ تم إرسال الذهب مؤخراً — تخطي")
        else:
            prices = get_prices(symbol)
            if prices:
                signal = determine_signal(prices, symbol)
                if signal:
                    send_telegram(format_message(symbol, signal))
                    mark_sent(symbol)
                else:
                    print("⏳ لا توجد فرصة واضحة في الذهب الآن")
            else:
                print(f"⚠️ لا توجد بيانات للذهب")

        time.sleep(20)

        # ── باقي الأسواق — كل 4 ساعات ───────────
        for symbol in ["XTI/USD", "EUR/USD", "GBP/USD"]:
            info = MARKETS[symbol]
            print(f"\n📊 تحليل {info['name']}...")

            if already_sent(symbol, hours=4):
                print(f"⏭️ تم إرسال {info['name']} مؤخراً — تخطي")
                time.sleep(5)
                continue

            prices = get_prices(symbol)
            if not prices:
                print(f"⚠️ لا توجد بيانات لـ {info['name']}")
                time.sleep(20)
                continue

            signal = determine_signal(prices, symbol)
            if signal:
                send_telegram(format_message(symbol, signal))
                mark_sent(symbol)
            else:
                print(f"⏳ لا توجد فرصة واضحة في {info['name']} الآن")
            time.sleep(20)

        print(f"\n✅ انتهت الدورة — الانتظار ساعة...")
        time.sleep(60 * 60)  # انتظر ساعة للدورة القادمة

if __name__ == "__main__":
    run()
