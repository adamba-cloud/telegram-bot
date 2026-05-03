import os
import logging
import sqlite3
import random
import asyncio
import threading
from datetime import datetime, timedelta

from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
    expiry TEXT,
    ref TEXT DEFAULT '',
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0
)
""")
conn.commit()

# ================= STATE =================
signal_data = {}
latest_signal = {}

# ================= DB =================
def ensure_user(uid, ref=""):
    user = cur.execute("SELECT id FROM users WHERE id=?", (uid,)).fetchone()

    if not user:
        acc = "ACC" + str(random.randint(100000, 999999))

        # 🎁 4 DAY FREE TRIAL
        expiry = (datetime.utcnow() + timedelta(days=4)).strftime("%Y-%m-%d")

        cur.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (uid, acc, "TRIAL", "active", expiry, ref, 0, 0)
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

# ================= ADMIN DASHBOARD =================
def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📡 Create Signal", callback_data="create_signal")],
        [InlineKeyboardButton("📊 Analytics", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 Users", callback_data="admin_users")]
    ])

# ================= USER MENU =================
def user_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Payment", callback_data="payment")],
        [InlineKeyboardButton("📞 Contact", callback_data="contact")],
        [InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard")],
        [InlineKeyboardButton("🔗 Referral", callback_data="ref")]
    ])

def signal_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 View Signal", callback_data="view_signal"),
            InlineKeyboardButton("📈 Chart", callback_data="chart")
        ],
        [
            InlineKeyboardButton("🏆 Stats", callback_data="stats")
        ]
    ])

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    ensure_user(uid)

    user = get_user(uid)

    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_text(
            "👑 ADMIN DASHBOARD\nFull Control Enabled",
            reply_markup=admin_menu()
        )
    else:
        await update.message.reply_text(
f"""
👋 WELCOME

ACCOUNT: {user[1]}
PLAN: {user[2]}
STATUS: {user[3]}
EXPIRY: {user[4]}

🎁 4 DAYS FREE TRIAL ACTIVE

VIP 👑 Instant Signals
BASIC 📊 Delayed Signals
""",
            reply_markup=user_menu()
        )

# ================= CALLBACKS =================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    ensure_user(uid)
    user = get_user(uid)

    # ===== ADMIN TOOLS =====
    if q.data == "admin_stats" and q.from_user.id == ADMIN_ID:
        total = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        await q.message.reply_text(f"📊 TOTAL USERS: {total}")

    elif q.data == "admin_users" and q.from_user.id == ADMIN_ID:
        users = cur.execute("SELECT id, plan, status FROM users LIMIT 10").fetchall()
        msg = "👥 USERS SAMPLE\n━━━━━━━━━━\n"
        for u in users:
            msg += f"{u[0]} | {u[1]} | {u[2]}\n"
        await q.message.reply_text(msg)

    # ===== USER ACTIONS =====
    elif q.data == "payment":
        await q.message.reply_text("💳 PAYBILL: 322372\nACCOUNT: Assigned Number")

    elif q.data == "contact":
        await q.message.reply_text(
            "📞 +254717434943 / +254781585319\nWhatsApp: +254717434943\nTikTok: smartgoldsignals"
        )

    elif q.data == "status":
        await q.message.reply_text(
            f"PLAN: {user[2]}\nSTATUS: {user[3]}\nEXPIRY: {user[4]}"
        )

    elif q.data == "ref":
        link = f"https://t.me/YourBot?start={uid}"
        await q.message.reply_text(f"🔗 Referral Link:\n{link}")

# ================= SIGNAL CREATION =================
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
        await update.message.reply_text("BUY or SELL:")

    elif step == "direction":
        signal_data[uid]["direction"] = text.upper()
        signal_data[uid]["step"] = "entry"
        await update.message.reply_text("ENTRY:")

    elif step == "entry":
        signal_data[uid]["entry"] = text
        signal_data[uid]["step"] = "tp"
        await update.message.reply_text("TP:")

    elif step == "tp":
        signal_data[uid]["tp"] = text
        signal_data[uid]["step"] = "sl"
        await update.message.reply_text("SL:")

    elif step == "sl":
        signal_data[uid]["sl"] = text

        signal = f"""
📊 {signal_data[uid]['pair']} | {signal_data[uid]['direction']} SETUP
━━━━━━━━━━━━━━
▢ Market Structure Confirmed
▢ Entry: {signal_data[uid]['entry']}
▢ TP: {signal_data[uid]['tp']}
▢ SL: {signal_data[uid]['sl']}
━━━━━━━━━━━━━━
📡 Powered by PESAMATRIX
"""

        users = cur.execute("SELECT id, plan, status FROM users").fetchall()

        for uid_db, plan, status in users:

            # ❗ BLOCK EXPIRED USERS
            if status != "active":
                continue

            if plan in ["VIP", "TRIAL"]:
                await context.bot.send_message(uid_db, signal, reply_markup=signal_buttons())

            elif plan == "BASIC":
                async def delayed(uid_db):
                    await asyncio.sleep(300)
                    await context.bot.send_message(uid_db, signal, reply_markup=signal_buttons())

                asyncio.create_task(delayed(uid_db))

        await update.message.reply_text("✅ Signal sent")
        del signal_data[uid]

# ================= EXPIRY AUTO CHECK =================
async def expiry_checker():
    while True:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        users = cur.execute("SELECT id, expiry FROM users").fetchall()

        for uid, exp in users:
            if exp and exp < today:
                cur.execute(
                    "UPDATE users SET status='expired', plan='none' WHERE id=?",
                    (uid,)
                )
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

    loop.create_task(expiry_checker())

asyncio.run_coroutine_threadsafe(startup(), loop)

# ================= HANDLERS =================
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CallbackQueryHandler(buttons))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_input))

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
