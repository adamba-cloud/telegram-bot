import os
import logging
import sqlite3
import random
import asyncio
import threading
from datetime import datetime

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

# ================= SIGNAL =================
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

# ================= MARKET =================
def market_status():
    hour = datetime.utcnow().hour
    return "📊 MARKET OPEN" if 6 <= hour <= 20 else "⛔ MARKET CLOSED"

# ================= MENU =================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📡 Signal", callback_data="signal")],
        [InlineKeyboardButton("💳 Payment", callback_data="payment")],
        [InlineKeyboardButton("📞 Contact", callback_data="contact")],
        [InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("💰 Confirm", callback_data="confirm")],
        [InlineKeyboardButton("📊 Market", callback_data="market")]
    ])

# ================= HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    ensure_user(uid)
    user = get_user(uid)

    await update.message.reply_text(
        f"🔥 WELCOME\n\nACCOUNT: {user[1]}\nPLAN: {user[2]}",
        reply_markup=main_menu()
    )

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    ensure_user(uid)
    user = get_user(uid)

    if q.data == "signal":
        if user[2] == "vip":
            await q.message.reply_text(generate_signal())
        elif user[2] == "basic":
            await asyncio.sleep(300)
            await q.message.reply_text(generate_signal())
        else:
            await q.message.reply_text("❌ Subscribe first")

    elif q.data == "payment":
        await q.message.reply_text("Paybill: 322372\nVIP: 1500\nBASIC: 500")

    elif q.data == "status":
        await q.message.reply_text(f"PLAN: {user[2]}")

    elif q.data == "market":
        await q.message.reply_text(market_status())

    elif q.data == "confirm":
        await context.bot.send_message(
            ADMIN_ID,
            f"Payment request\nUSER: {uid}"
        )
        await q.message.reply_text("Sent to admin")

async def media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    file_id = None
    if update.message.photo:
        file_id = update.message.photo[-1].file_id

    if not file_id:
        return

    await context.bot.send_photo(PUBLIC_CHANNEL, file_id)

# ================= FLASK WEBHOOK =================
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, telegram_app.bot)

    asyncio.run_coroutine_threadsafe(
        telegram_app.process_update(update),
        loop
    )

    return "ok"

@app.route("/")
def home():
    return "Bot Running"

# ================= EVENT LOOP THREAD =================
def run_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

loop = asyncio.new_event_loop()
threading.Thread(target=run_loop, args=(loop,), daemon=True).start()

# ================= START BOT =================
async def startup():
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    logging.info("Bot started")

asyncio.run_coroutine_threadsafe(startup(), loop)

# ================= HANDLERS =================
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CallbackQueryHandler(buttons))
telegram_app.add_handler(MessageHandler(filters.PHOTO, media))

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
