import os
import logging
import sqlite3
import random
import asyncio
from datetime import datetime, timedelta

from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not BOT_TOKEN or not WEBHOOK_URL:
    raise ValueError("Missing BOT_TOKEN or WEBHOOK_URL")

ADMIN_ID = 8633049548

VIP_CHANNEL = -1003962643374
BASIC_CHANNEL = -1003965211730
PUBLIC_CHANNEL = -1003950150130
REGISTRY_CHANNEL = -1003834556396

SIGNAL_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "BTCUSD"]

logging.basicConfig(level=logging.INFO)

# ================= APP =================
app = Flask(__name__)
telegram_app = Application.builder().token(BOT_TOKEN).build()

# ================= DATABASE =================
conn = sqlite3.connect("users.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    account TEXT,
    plan TEXT,
    status TEXT,
    expiry TEXT
)
""")
conn.commit()

def ensure_user(uid):
    if not cur.execute("SELECT id FROM users WHERE id=?", (uid,)).fetchone():
        acc = "ACC" + uid[-6:]
        cur.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?)",
            (uid, acc, "none", "registered", "")
        )
        conn.commit()

def get_user(uid):
    return cur.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

def update_user(uid, **kwargs):
    keys = ", ".join([f"{k}=?" for k in kwargs])
    values = list(kwargs.values())
    values.append(uid)
    cur.execute(f"UPDATE users SET {keys} WHERE id=?", values)
    conn.commit()

# ================= SIGNAL ENGINE =================
def generate_signal():
    pair = random.choice(SIGNAL_PAIRS)
    direction = random.choice(["BUY 📈", "SELL 📉"])
    entry = round(random.uniform(100, 2000), 2)
    sl = round(entry - random.uniform(10, 30), 2)
    tp = round(entry + random.uniform(20, 60), 2)

    return f"""
📡 TRADE SIGNAL
━━━━━━━━━━━━
PAIR: {pair}
DIRECTION: {direction}
ENTRY: {entry}
TP: {tp}
SL: {sl}
━━━━━━━━━━━━
"""

# ================= MARKET STATUS =================
def market_status():
    hour = datetime.utcnow().hour
    if 6 <= hour <= 20:
        return "📊 MARKET OPEN / TRADING ACTIVE"
    else:
        return "⛔ MARKET CLOSED"

# ================= MENU =================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📡 Signal", callback_data="signal")],
        [InlineKeyboardButton("💳 Payment Methods", callback_data="payment")],
        [InlineKeyboardButton("📞 Contacts", callback_data="contact")],
        [InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("💰 Confirm Payment", callback_data="confirm")],
        [InlineKeyboardButton("📊 Market Status", callback_data="market")]
    ])

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    ensure_user(uid)

    user = get_user(uid)

    await update.message.reply_text(
        f"🔥 WELCOME\n\n"
        f"ACCOUNT: {user[1]}\n"
        f"STATUS: {user[3]}\n"
        f"PLAN: {user[2]}",
        reply_markup=main_menu()
    )

# ================= BUTTONS =================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    ensure_user(uid)
    user = get_user(uid)

    # SIGNAL
    if q.data == "signal":
        if user[2] == "vip":
            await q.message.reply_text(generate_signal())
        elif user[2] == "basic":
            await asyncio.sleep(300)  # 5 min delay
            await q.message.reply_text(generate_signal())
        else:
            await q.message.reply_text("❌ Subscribe first")

    # PAYMENT METHODS
    elif q.data == "payment":
        await q.message.reply_text(
            "💳 PAYMENT DETAILS\n\n"
            "Paybill: 322372\n"
            "Account: YOUR GENERATED ACCOUNT NUMBER\n\n"
            "VIP: Ksh 1500 / month\n"
            "BASIC: Ksh 500 / week"
        )

    # CONTACTS
    elif q.data == "contact":
        await q.message.reply_text(
            "📞 CONTACTS\n\n"
            "Admin: @yourusername\n"
            "Support: support@tradingbot.com"
        )

    # STATUS
    elif q.data == "status":
        await q.message.reply_text(
            f"📊 STATUS\n\nPLAN: {user[2]}\nACCOUNT: {user[1]}\nSTATE: {user[3]}"
        )

    # MARKET STATUS
    elif q.data == "market":
        await q.message.reply_text(market_status())

    # PAYMENT CONFIRMATION
    elif q.data == "confirm":
        await telegram_app.bot.send_message(
            ADMIN_ID,
            f"💰 PAYMENT CONFIRMATION REQUEST\n\nUSER: {uid}\nACCOUNT: {user[1]}"
        )
        await q.message.reply_text("📩 Sent to admin for approval")

# ================= MEDIA HANDLER =================
async def media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    caption = update.message.caption or ""
    file_id = None

    if update.message.photo:
        file_id = update.message.photo[-1].file_id

    if update.message.video:
        file_id = update.message.video.file_id

    if not file_id:
        return

    if "VIP" in caption:
        await telegram_app.bot.send_photo(VIP_CHANNEL, file_id, caption=caption)
    elif "BASIC" in caption:
        await telegram_app.bot.send_photo(BASIC_CHANNEL, file_id, caption=caption)
    elif "PUBLIC" in caption:
        await telegram_app.bot.send_photo(PUBLIC_CHANNEL, file_id, caption=caption)
    else:
        await telegram_app.bot.send_photo(PUBLIC_CHANNEL, file_id, caption=caption)

# ================= WEBHOOK =================
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, telegram_app.bot)

    asyncio.run(telegram_app.process_update(update))
    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "Bot Running"

# ================= STARTUP =================
async def on_startup():
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    logging.info("Webhook active")

def main():
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CallbackQueryHandler(buttons))
    telegram_app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, media))

    import asyncio
    asyncio.run(on_startup())

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
