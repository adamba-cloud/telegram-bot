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
TYPE: {direction}
ENTRY: {entry}
TP: {tp}
SL: {sl}
━━━━━━━━━━━━
"""

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
        [InlineKeyboardButton("📡 Send Signal", callback_data="send_signal")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]
    ])

# ================= HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    ensure_user(uid)
    user = get_user(uid)

    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_text("👑 ADMIN DASHBOARD", reply_markup=admin_menu())
    else:
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

    # ===== USER =====
    if q.data == "payment":
        await q.message.reply_text(
            f"Paybill: 322372\nAccount: {user[1]}\n\nVIP: 1500 (30 days)\nBASIC: 500 (7 days)"
        )

    elif q.data == "contact":
        await q.message.reply_text(
            "📞 CONTACT\n\n"
            "+254781585319\n"
            "+254717434943\n"
            "TikTok: https://tiktok.com/@smartgoldsignals"
        )

    elif q.data == "status":
        await q.message.reply_text(
            f"PLAN: {user[2]}\nSTATUS: {user[3]}\nEXPIRY: {user[4]}"
        )

    elif q.data == "confirm":
        await context.bot.send_message(
            ADMIN_ID,
            f"💰 PAYMENT REQUEST\nUSER: {uid}\nACCOUNT: {user[1]}",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Approve VIP", callback_data=f"approve_vip_{uid}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}")
                ],
                [
                    InlineKeyboardButton("✅ Approve BASIC", callback_data=f"approve_basic_{uid}")
                ]
            ])
        )
        await q.message.reply_text("Sent to admin")

    # ===== ADMIN =====
    elif q.data == "send_signal":
        signal = generate_signal()
        await context.bot.send_message(VIP_CHANNEL, signal)
        await context.bot.send_message(BASIC_CHANNEL, signal)
        await context.bot.send_message(PUBLIC_CHANNEL, signal)
        await q.message.reply_text("Signal sent")

    elif q.data.startswith("approve_vip"):
        user_id = q.data.split("_")[2]
        update_user(user_id, "VIP", "active", 30)

        await context.bot.send_message(user_id, "✅ VIP Activated (30 days)")
        await context.bot.send_message(REGISTRY_CHANNEL, f"VIP USER: {user_id}")
        await q.message.reply_text("Approved VIP")

    elif q.data.startswith("approve_basic"):
        user_id = q.data.split("_")[2]
        update_user(user_id, "BASIC", "active", 7)

        await context.bot.send_message(user_id, "✅ BASIC Activated (7 days)")
        await context.bot.send_message(REGISTRY_CHANNEL, f"BASIC USER: {user_id}")
        await q.message.reply_text("Approved BASIC")

    elif q.data.startswith("reject"):
        user_id = q.data.split("_")[1]
        await context.bot.send_message(user_id, "❌ Payment rejected")
        await q.message.reply_text("Rejected")

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
    else:
        await send(PUBLIC_CHANNEL, file_id, caption=caption)

# ================= AUTO EXPIRY =================
async def expiry_check():
    while True:
        now = datetime.utcnow().strftime("%Y-%m-%d")
        users = cur.execute("SELECT id, expiry FROM users").fetchall()

        for uid, exp in users:
            if exp and exp < now:
                cur.execute("UPDATE users SET plan='none', status='expired' WHERE id=?", (uid,))
                conn.commit()

        await asyncio.sleep(3600)

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
    loop.create_task(expiry_check())

asyncio.run_coroutine_threadsafe(startup(), loop)

# ================= HANDLERS =================
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CallbackQueryHandler(buttons))
telegram_app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, media))

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
