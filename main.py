import os
import logging
import sqlite3
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEB_APP_URL = os.getenv("WEB_APP_URL")

ADMIN_ID = 8633049548

logging.basicConfig(level=logging.INFO)

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing")

# ================= DATABASE =================
conn = sqlite3.connect("users.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    plan TEXT,
    status TEXT
)
""")
conn.commit()

# ================= HELPERS =================
def ensure_user(uid):
    user = cur.execute("SELECT id FROM users WHERE id=?", (uid,)).fetchone()
    if not user:
        cur.execute(
            "INSERT INTO users VALUES (?, ?, ?)",
            (uid, "TRIAL", "active")
        )
        conn.commit()

def get_user(uid):
    return cur.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

# ================= UI =================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Signal", callback_data="signal")],
        [InlineKeyboardButton("💳 Payment", callback_data="payment")],
        [InlineKeyboardButton("📞 Contact", callback_data="contact")],
        [InlineKeyboardButton("📈 Status", callback_data="status")]
    ])

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    ensure_user(uid)
    user = get_user(uid)

    await update.message.reply_text(
        f"""
💎 WELCOME TO PESAMATRIX

USER ID: {uid}
PLAN: {user[1]}
STATUS: {user[2]}

Choose an option below:
""",
        reply_markup=main_menu()
    )

# ================= SIGNAL (BACKEND) =================
async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not WEB_APP_URL:
            return await update.message.reply_text("⚠️ WEB_APP_URL not set")

        res = requests.get(f"{WEB_APP_URL}/ai-signal", timeout=10)
        data = res.json()

        msg = f"""
📊 LIVE SIGNAL

PAIR: {data['pair']}
DIRECTION: {data['direction']}
ENTRY: {data['entry']}
TP: {data['tp']}
SL: {data['sl']}
"""

        await update.message.reply_text(msg)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Backend error: {e}")

# ================= CALLBACKS =================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    ensure_user(uid)
    user = get_user(uid)

    if q.data == "signal":
        await signal(update, context)

    elif q.data == "payment":
        await q.message.reply_text(
            "💳 PAYBILL: 322372\nACCOUNT: PESAMATRIX"
        )

    elif q.data == "contact":
        await q.message.reply_text(
            "📞 +254717434943\nWhatsApp: +254717434943"
        )

    elif q.data == "status":
        await q.message.reply_text(
            f"PLAN: {user[1]}\nSTATUS: {user[2]}"
        )

# ================= ADMIN =================
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("Admin active. Use /signal")

# ================= MAIN =================
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("signal", signal))
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CallbackQueryHandler(buttons))

    print("🤖 Bot running (polling mode)...")
    application.run_polling()

# ================= RUN =================
if __name__ == "__main__":
    main()
