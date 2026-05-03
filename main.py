import os
import logging
import sqlite3
import random
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

ADMIN_ID = 8633049548

VIP_CHANNEL_ID = -1003962643374

BRAND = "🔥💰 PESAMATRIX COPY ENGINE 💰🔥"

PLANS = {
    "trial": 3,
    "basic": 7,
    "vip": 30
}

SIGNAL_PAIRS = ["EURUSD", "GBPUSD", "BTCUSD", "XAUUSD"]

# ================= LOGGING =================
logging.basicConfig(level=logging.INFO)

# ================= DB =================
conn = sqlite3.connect("users.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    plan TEXT,
    expiry TEXT,
    pending_plan TEXT,
    mpesa_code TEXT
)
""")
conn.commit()


def get_user(uid):
    cur.execute("SELECT * FROM users WHERE id=?", (uid,))
    return cur.fetchone()


def ensure_user(uid):
    if not get_user(uid):
        cur.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?)",
            (uid, "none", "", "", "")
        )
        conn.commit()


def update_user(uid, field, value):
    cur.execute(f"UPDATE users SET {field}=? WHERE id=?", (value, uid))
    conn.commit()


def is_active(expiry):
    try:
        return datetime.fromisoformat(expiry) > datetime.now()
    except:
        return False


# ================= BOT =================
app = Application.builder().token(BOT_TOKEN).build()

# ================= UI BUTTONS =================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Subscribe", callback_data="subscribe")],
        [InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("📡 Signals", callback_data="signals")],
        [InlineKeyboardButton("💰 Payment", callback_data="payment")]
    ])


def plan_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Trial (3d)", callback_data="trial")],
        [InlineKeyboardButton("Basic (7d)", callback_data="basic")],
        [InlineKeyboardButton("VIP (30d)", callback_data="vip")]
    ])


# ================= SIGNAL ENGINE =================
def generate_signal():
    pair = random.choice(SIGNAL_PAIRS)
    direction = random.choice(["BUY 📈", "SELL 📉"])
    confidence = random.randint(70, 95)
    return f"📡 SIGNAL\nPAIR: {pair}\nACTION: {direction}\nCONFIDENCE: {confidence}%"


# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    ensure_user(uid)

    await update.message.reply_text(
        f"{BRAND}\nWelcome to Trading Bot 🚀",
        reply_markup=main_menu()
    )


async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    ensure_user(uid)

    if q.data == "subscribe":
        await q.message.reply_text("Choose plan:", reply_markup=plan_menu())

    elif q.data == "status":
        user = get_user(uid)
        status = "ACTIVE" if is_active(user[2]) else "DORMANT"
        await q.message.reply_text(
            f"PLAN: {user[1]}\nSTATUS: {status}\nEXPIRY: {user[2]}"
        )

    elif q.data == "payment":
        await q.message.reply_text(
            "Send M-Pesa to PAYBILL: 322372\nThen send transaction code."
        )

    elif q.data == "signals":
        user = get_user(uid)

        if not is_active(user[2]):
            await q.message.reply_text("❌ You need active subscription")
            return

        await q.message.reply_text(generate_signal())


async def select_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    ensure_user(uid)

    update_user(uid, "pending_plan", q.data)

    await q.message.reply_text(
        f"Send payment to PAYBILL 322372\nThen send M-Pesa code."
    )


async def payment_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    code = update.message.text

    update_user(uid, "mpesa_code", code)

    await context.bot.send_message(
        ADMIN_ID,
        f"💰 PAYMENT RECEIVED\nUSER: {uid}\nCODE: {code}"
    )

    await update.message.reply_text("Waiting approval...")


async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    uid = context.args[0]

    cur.execute("SELECT pending_plan FROM users WHERE id=?", (uid,))
    plan = cur.fetchone()[0]

    expiry = datetime.now() + timedelta(days=PLANS[plan])

    update_user(uid, "plan", plan)
    update_user(uid, "expiry", expiry.isoformat())

    await context.bot.send_message(uid, "✅ Activated VIP access")


# ================= HANDLERS =================
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("approve", approve))

app.add_handler(CallbackQueryHandler(handle_buttons, pattern="^(subscribe|status|payment|signals)$"))
app.add_handler(CallbackQueryHandler(select_plan, pattern="^(trial|basic|vip)$"))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, payment_code))


# ================= FLASK =================
flask_app = Flask(__name__)


@app.route("/", methods=["GET"])
def home():
    return "Bot running"


@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(), app.bot)
    app.update_queue.put(update)
    return "ok"


# ================= START WEBHOOK =================
async def start_bot():
    await app.initialize()
    await app.start()
    await app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")


if __name__ == "__main__":
    import asyncio

    asyncio.get_event_loop().run_until_complete(start_bot())

    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)
