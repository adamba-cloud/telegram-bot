import os
import logging
import sqlite3
import random
import asyncio
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

ADMIN_ID = 8633049548

VIP_CHANNEL = -1003962643374
BASIC_CHANNEL = -1003965211730
PUBLIC_CHANNEL = -1003950150130
REGISTRY_CHANNEL = -1003834556396

SIGNAL_PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "BTCUSD",
    "AUDUSD", "USDCHF", "USDCAD", "NZDUSD"
]

logging.basicConfig(level=logging.INFO)

# ================= DATABASE =================
conn = sqlite3.connect("users.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    plan TEXT,
    expiry TEXT,
    account TEXT
)
""")
conn.commit()


def ensure_user(uid):
    if not cur.execute("SELECT id FROM users WHERE id=?", (uid,)).fetchone():
        cur.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?)",
            (uid, "none", "", "PMX" + uid[-6:])
        )
        conn.commit()


def get_user(uid):
    return cur.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()


def is_active(expiry):
    try:
        return datetime.fromisoformat(expiry) > datetime.now()
    except:
        return False


# ================= BOT =================
app = Application.builder().token(BOT_TOKEN).build()

# ================= SIGNAL ENGINE =================
def generate_signal():
    pair = random.choice(SIGNAL_PAIRS)
    direction = random.choice(["BUY 📈", "SELL 📉"])

    base_price = random.uniform(1.0, 2000.0)
    entry = round(base_price, 5)

    if direction.startswith("BUY"):
        sl = round(entry - random.uniform(0.5, 2.0), 5)
        tp1 = round(entry + random.uniform(1.0, 3.0), 5)
        tp2 = round(entry + random.uniform(3.0, 6.0), 5)
    else:
        sl = round(entry + random.uniform(0.5, 2.0), 5)
        tp1 = round(entry - random.uniform(1.0, 3.0), 5)
        tp2 = round(entry - random.uniform(3.0, 6.0), 5)

    confidence = random.randint(75, 97)

    return (
        f"📡 TRADE SIGNAL\n"
        f"━━━━━━━━━━━━━━\n"
        f"PAIR: {pair}\n"
        f"DIRECTION: {direction}\n\n"
        f"ENTRY: {entry}\n"
        f"TP1: {tp1}\n"
        f"TP2: {tp2}\n"
        f"SL: {sl}\n\n"
        f"CONFIDENCE: {confidence}%\n"
        f"━━━━━━━━━━━━━━"
    )


# ================= CHANNELS =================
async def send_to_channels(text, delay_basic=False):
    await app.bot.send_message(VIP_CHANNEL, text)

    if delay_basic:
        await asyncio.sleep(300)

    await app.bot.send_message(BASIC_CHANNEL, text)


# ================= MEDIA =================
async def send_media(file_id, caption, target):
    targets = {
        "VIP": VIP_CHANNEL,
        "BASIC": BASIC_CHANNEL,
        "PUBLIC": PUBLIC_CHANNEL,
        "ALL": [VIP_CHANNEL, BASIC_CHANNEL, PUBLIC_CHANNEL]
    }

    if target == "ALL":
        for ch in targets["ALL"]:
            await app.bot.send_photo(ch, file_id, caption=caption)
    else:
        await app.bot.send_photo(targets[target], file_id, caption=caption)


# ================= UI =================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📡 Get Signal", callback_data="signal")],
        [InlineKeyboardButton("📊 Status", callback_data="status")]
    ])


# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    ensure_user(uid)
    user = get_user(uid)

    await update.message.reply_text(
        f"🔥 TRADING SYSTEM\n\n"
        f"👤 ACCOUNT: {user[3]}\n"
        f"📦 PLAN: {user[1]}",
        reply_markup=main_menu()
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    ensure_user(uid)
    user = get_user(uid)

    if q.data == "signal":
        if user[1] == "vip":
            await send_to_channels(generate_signal(), delay_basic=False)
            await q.message.reply_text("📡 VIP signal sent")
        elif user[1] == "basic":
            await send_to_channels(generate_signal(), delay_basic=True)
            await q.message.reply_text("📡 BASIC signal (delayed)")
        else:
            await q.message.reply_text("❌ Subscribe first")

    elif q.data == "status":
        await q.message.reply_text(
            f"PLAN: {user[1]}\nACCOUNT: {user[3]}"
        )


# ================= ADMIN SIGNAL =================
async def admin_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    await send_to_channels(generate_signal(), delay_basic=True)


# ================= MEDIA =================
async def media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not update.message.photo:
        return

    file_id = update.message.photo[-1].file_id
    caption = update.message.caption or ""

    if "VIP" in caption:
        await send_media(file_id, caption, "VIP")
    elif "BASIC" in caption:
        await send_media(file_id, caption, "BASIC")
    elif "PUBLIC" in caption:
        await send_media(file_id, caption, "PUBLIC")
    else:
        await send_media(file_id, caption, "ALL")


# ================= HANDLERS =================
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("signal", admin_signal))
app.add_handler(CallbackQueryHandler(buttons))
app.add_handler(MessageHandler(filters.PHOTO, media))


# ================= FLASK WEBHOOK (FIXED) =================
flask_app = Flask(__name__)


@app.route("/", methods=["GET"])
def home():
    return "Bot Running"


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, app.bot)

    # ✅ FIX: proper async execution (NO update_queue)
    app.create_task(app.process_update(update))

    return "ok"


# ================= START =================
async def start_bot():
    await app.initialize()
    await app.start()

    await app.bot.set_webhook(
        url=f"{WEBHOOK_URL}/webhook"
    )


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_bot())

    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)
