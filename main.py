import os
import logging
import sqlite3
import random
import asyncio
import threading
from datetime import datetime, timedelta

from flask import Flask, request
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

ADMIN_ID = 8633049548

VIP_CHANNEL = -1003962643374
BASIC_CHANNEL = -1003965211730
PUBLIC_CHANNEL = -1003950150130
REGISTRY_CHANNEL = -1003834556396

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

# ================= SIGNAL STATE =================
signal_data = {}

# ================= DB FUNCTIONS =================
def ensure_user(uid):
    if not cur.execute("SELECT id FROM users WHERE id=?", (uid,)).fetchone():
        acc = "ACC" + str(random.randint(100000, 999999))
        cur.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?)",
            (uid, acc, "none", "registered", "")
        )
        conn.commit()

def get_user(uid):
    return cur.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

def update_user(uid, plan, status, days):
    expiry = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d")
    cur.execute(
        "UPDATE users SET plan=?, status=?, expiry=? WHERE id=?",
        (plan, status, expiry, uid)
    )
    conn.commit()

# ================= MENUS =================
def user_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Payment", callback_data="payment")],
        [InlineKeyboardButton("📞 Contact", callback_data="contact")],
        [InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("💰 Confirm", callback_data="confirm")]
    ])

def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📡 Send Signal", callback_data="send_signal")]
    ])

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    ensure_user(uid)

    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_text("👑 ADMIN", reply_markup=admin_menu())
    else:
        user = get_user(uid)
        await update.message.reply_text(
            f"ACCOUNT: {user[1]}\nPLAN: {user[2]}",
            reply_markup=user_menu()
        )

# ================= BUTTONS =================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    ensure_user(uid)
    user = get_user(uid)

    if q.data == "send_signal":
        if q.from_user.id != ADMIN_ID:
            return
        signal_data[uid] = {"step": "pair"}
        await q.message.reply_text("Enter PAIR (e.g XAUUSD):")

# ================= ADMIN INPUT =================
async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    uid = str(update.effective_user.id)

    if uid not in signal_data:
        return

    text = update.message.text

    step = signal_data[uid]["step"]

    if step == "pair":
        signal_data[uid]["pair"] = text.upper()
        signal_data[uid]["step"] = "direction"
        await update.message.reply_text("Enter Direction (BUY/SELL):")

    elif step == "direction":
        signal_data[uid]["direction"] = text.upper()
        signal_data[uid]["step"] = "entry"
        await update.message.reply_text("Enter ENTRY:")

    elif step == "entry":
        signal_data[uid]["entry"] = text
        signal_data[uid]["step"] = "tp"
        await update.message.reply_text("Enter TP:")

    elif step == "tp":
        signal_data[uid]["tp"] = text
        signal_data[uid]["step"] = "sl"
        await update.message.reply_text("Enter SL:")

    elif step == "sl":
        signal_data[uid]["sl"] = text

        signal = f"""
📡 TRADE SIGNAL
━━━━━━━━━━━━
PAIR: {signal_data[uid]['pair']}
TYPE: {signal_data[uid]['direction']}
ENTRY: {signal_data[uid]['entry']}
TP: {signal_data[uid]['tp']}
SL: {signal_data[uid]['sl']}
━━━━━━━━━━━━
"""

        # VIP instant
        await context.bot.send_message(VIP_CHANNEL, signal)

        # BASIC delayed
        async def send_basic():
            await asyncio.sleep(300)
            await context.bot.send_message(BASIC_CHANNEL, signal)

        asyncio.create_task(send_basic())

        await update.message.reply_text("✅ Signal sent")

        del signal_data[uid]

# ================= MEDIA =================
async def media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    caption = update.message.caption or ""

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        send = context.bot.send_photo
    elif update.message.video:
        file_id = update.message.video.file_id
        send = context.bot.send_video
    else:
        return

    if "VIP" in caption:
        await send(VIP_CHANNEL, file_id, caption=caption)
    elif "BASIC" in caption:
        await send(BASIC_CHANNEL, file_id, caption=caption)

# ================= WEBHOOK =================
@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    asyncio.run_coroutine_threadsafe(telegram_app.process_update(update), loop)
    return "ok"

@app.route("/")
def home():
    return "Bot Running"

# ================= LOOP =================
def run_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

loop = asyncio.new_event_loop()
threading.Thread(target=run_loop, args=(loop,), daemon=True).start()

# ================= START =================
async def startup():
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")

asyncio.run_coroutine_threadsafe(startup(), loop)

# ================= HANDLERS =================
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CallbackQueryHandler(buttons))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_input))
telegram_app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, media))

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
