import os
import logging
import sqlite3
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
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://your-app.onrender.com

ADMIN_ID = 8633049548

VIP_CHANNEL_ID = -1003962643374
REGISTRY_CHANNEL_ID = -1003834556396

PAYBILL = "322372"
CONTACT = "+254781585319 / +254717434943"

BRAND = "🔥💰 PESAMATRIX COPY ENGINE 💰🔥"

PLANS = {"trial": 3, "basic": 7, "vip": 30}

# ================= LOGGING =================
logging.basicConfig(level=logging.INFO)

# ================= DB (SQLite - NO DATA LOSS) =================
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
    row = cur.fetchone()
    return row


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


# ================= BOT APP =================
app = Application.builder().token(BOT_TOKEN).build()

# ================= UI =================
def dashboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Subscribe", callback_data="subscribe")],
        [InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("💰 Payment", callback_data="payment")]
    ])


# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    ensure_user(uid)

    await update.message.reply_text(
        f"{BRAND}\nWelcome",
        reply_markup=dashboard()
    )


# ================= MENU =================
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    ensure_user(uid)

    cur.execute("SELECT * FROM users WHERE id=?", (uid,))
    user = cur.fetchone()

    if q.data == "subscribe":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Trial", callback_data="trial")],
            [InlineKeyboardButton("Basic", callback_data="basic")],
            [InlineKeyboardButton("VIP", callback_data="vip")]
        ])
        await q.message.reply_text("Choose plan:", reply_markup=kb)

    elif q.data == "status":
        status = "ACTIVE" if is_active(user[2]) else "DORMANT"
        await q.message.reply_text(f"PLAN: {user[1]}\nSTATUS: {status}")

    elif q.data == "payment":
        await q.message.reply_text(f"PAYBILL: {PAYBILL}")


# ================= PLAN =================
async def plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)

    update_user(uid, "pending_plan", q.data)

    await q.message.reply_text(
        f"Send payment to {PAYBILL}\nThen send M-Pesa code."
    )


# ================= PAYMENT =================
async def payment_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    code = update.message.text

    update_user(uid, "mpesa_code", code)

    await context.bot.send_message(
        ADMIN_ID,
        f"PAYMENT\nUSER: {uid}\nCODE: {code}"
    )

    await update.message.reply_text("Waiting approval...")


# ================= APPROVE =================
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    uid = context.args[0]

    cur.execute("SELECT pending_plan FROM users WHERE id=?", (uid,))
    plan = cur.fetchone()[0] or "basic"

    expiry = datetime.now() + timedelta(days=PLANS[plan])

    update_user(uid, "plan", plan)
    update_user(uid, "expiry", expiry.isoformat())

    await context.bot.send_message(uid, "✅ ACTIVATED")


# ================= HANDLERS =================
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("approve", approve))

app.add_handler(CallbackQueryHandler(menu, pattern="^(subscribe|status|payment)$"))
app.add_handler(CallbackQueryHandler(plan, pattern="^(trial|basic|vip)$"))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, payment_code))


# ================= FLASK WEBHOOK =================
flask_app = Flask(__name__)


@flask_app.post("/webhook")
def webhook():
    update = Update.de_json(request.get_json(), app.bot)
    app.process_update(update)
    return "ok"


# ================= START WEBHOOK =================
async def on_startup():
    await app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")


if __name__ == "__main__":
    import asyncio

    asyncio.get_event_loop().run_until_complete(on_startup())

    flask_app.run(host="0.0.0.0", port=10000)
