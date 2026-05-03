import os
import logging
import sqlite3
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

ADMIN_ID = 8633049548

VIP_CHANNEL_ID = -1003962643374
REGISTRY_CHANNEL_ID = -1003834556396

PAYBILL = "322372"
CONTACT = "+254781585319 / +254717434943"

BRAND = "🔥💰 PESAMATRIX COPY ENGINE 💰🔥"
PLANS = {"trial": 3, "basic": 7, "vip": 30}

# ================= VALIDATION =================
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set")

if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL not set")

# ================= LOGGING =================
logging.basicConfig(level=logging.INFO)

# ================= DATABASE =================
conn = sqlite3.connect("users.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    plan TEXT,
    expiry TEXT,
    account TEXT,
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
            "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
            (uid, "none", "", "PMX" + uid[-6:], "", "")
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
telegram_app = Application.builder().token(BOT_TOKEN).build()

# ================= UI =================
def dashboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Subscribe", callback_data="subscribe")],
        [InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("💰 Payment", callback_data="payment")]
    ])


# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    ensure_user(uid)

    await update.message.reply_text(
        f"{BRAND}\nWelcome\n\nContact: {CONTACT}",
        reply_markup=dashboard()
    )


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    ensure_user(uid)

    user = get_user(uid)

    if q.data == "subscribe":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Trial", callback_data="trial")],
            [InlineKeyboardButton("Basic", callback_data="basic")],
            [InlineKeyboardButton("VIP", callback_data="vip")]
        ])
        await q.message.reply_text("Choose plan:", reply_markup=kb)

    elif q.data == "status":
        status = "ACTIVE" if is_active(user[2]) else "DORMANT"
        await q.message.reply_text(
            f"PLAN: {user[1]}\nSTATUS: {status}\nEXPIRY: {user[2]}"
        )

    elif q.data == "payment":
        await q.message.reply_text(
            f"PAYBILL: {PAYBILL}\nSend payment then send M-Pesa code.\n\nSupport: {CONTACT}"
        )


async def plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    update_user(uid, "pending_plan", q.data)

    await q.message.reply_text(
        f"Send payment to PAYBILL {PAYBILL}\nThen send M-Pesa code."
    )


async def payment_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    code = update.message.text

    update_user(uid, "mpesa_code", code)

    await context.bot.send_message(
        ADMIN_ID,
        f"💰 PAYMENT ALERT\nUSER: {uid}\nCODE: {code}"
    )

    await update.message.reply_text("Waiting admin approval...")


async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Usage: /approve USER_ID")
        return

    uid = context.args[0]

    cur.execute("SELECT pending_plan FROM users WHERE id=?", (uid,))
    result = cur.fetchone()

    if not result:
        await update.message.reply_text("User not found")
        return

    plan = result[0] or "basic"
    expiry = datetime.now() + timedelta(days=PLANS[plan])

    update_user(uid, "plan", plan)
    update_user(uid, "expiry", expiry.isoformat())

    # 🔥 Add user to VIP channel (optional)
    try:
        await context.bot.unban_chat_member(VIP_CHANNEL_ID, int(uid))
    except:
        pass

    await context.bot.send_message(uid, "✅ ACTIVATED")


# ================= HANDLERS =================
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("approve", approve))

telegram_app.add_handler(CallbackQueryHandler(menu, pattern="^(subscribe|status|payment)$"))
telegram_app.add_handler(CallbackQueryHandler(plan, pattern="^(trial|basic|vip)$"))

telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, payment_code))


# ================= FLASK =================
flask_app = Flask(__name__)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)


@flask_app.route("/", methods=["GET"])
def home():
    return "Bot is running"


@flask_app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    update = Update.de_json(data, telegram_app.bot)
    loop.run_until_complete(telegram_app.process_update(update))
    return "ok"


# ================= START =================
async def start_bot():
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")


if __name__ == "__main__":
    loop.run_until_complete(start_bot())

    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)
