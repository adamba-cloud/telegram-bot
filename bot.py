import os
import json
import random
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8633049548

VIP_CHANNEL_ID = -1003962643374
BASIC_CHANNEL_ID = -1003965211730
PUBLIC_CHANNEL_ID = -1003950150130
REGISTRY_CHANNEL_ID = -1003834556396

USERS_FILE = "users.json"

PAYBILL = "322372"
CONTACT = "+254781585319 / +254717434943"
TIKTOK = "https://tiktok.com/@smartgoldsignals"

BRAND = "🔥💰 PESAMATRIX COPY ENGINE 💰🔥\nPOWERED BY PESAMATRIX"

PLANS = {"trial": 3, "basic": 7, "vip": 30}

ENTER_CODE = 1

# ================= DATABASE =================
def load_users():
    if os.path.exists(USERS_FILE):
        try:
            return json.load(open(USERS_FILE))
        except:
            return {}
    return {}

def save_users():
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

users = load_users()

def ensure_user(uid):
    if uid not in users:
        users[uid] = {
            "plan": "none",
            "expiry": "",
            "account": "PMX" + str(random.randint(100000, 999999))
        }
        save_users()

def is_active(user):
    try:
        return datetime.fromisoformat(user["expiry"]) > datetime.now()
    except:
        return False

# ================= UI =================
def dashboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Subscribe", callback_data="subscribe")],
        [InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("💰 Payment", callback_data="payment")],
        [InlineKeyboardButton("📞 Contact", callback_data="contact")]
    ])

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    ensure_user(uid)

    try:
        await context.bot.send_message(
            REGISTRY_CHANNEL_ID,
            f"🆕 NEW USER\nID: {uid}\nACCOUNT: {users[uid]['account']}"
        )
    except:
        pass

    await update.message.reply_text(
        f"{BRAND}\n\nWelcome 🔥\n\nAccount: {users[uid]['account']}",
        reply_markup=dashboard()
    )

# ================= MENU =================
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    ensure_user(uid)
    user = users[uid]

    if q.data == "subscribe":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧪 Trial", callback_data="trial")],
            [InlineKeyboardButton("💰 Basic", callback_data="basic")],
            [InlineKeyboardButton("💎 VIP", callback_data="vip")]
        ])
        await q.message.reply_text("Choose plan:", reply_markup=kb)

    elif q.data == "status":
        await q.message.reply_text(
            f"PLAN: {user['plan']}\n"
            f"STATUS: {'ACTIVE' if is_active(user) else 'DORMANT'}\n"
            f"ACCOUNT: {user['account']}"
        )

    elif q.data == "payment":
        await q.message.reply_text(
            f"PAYBILL: {PAYBILL}\nACCOUNT: {user['account']}"
        )

    elif q.data == "contact":
        await q.message.reply_text(f"{CONTACT}\n{TIKTOK}")

# ================= PLAN SELECT =================
async def plan_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data not in ["trial", "basic", "vip"]:
        return  # prevents conflict

    uid = str(q.from_user.id)
    ensure_user(uid)

    users[uid]["pending_plan"] = q.data
    save_users()

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm Payment", callback_data="confirm")]
    ])

    await q.message.reply_text(
        f"PAY TO:\n{PAYBILL}\nACCOUNT: {users[uid]['account']}",
        reply_markup=kb
    )

# ================= CONFIRM =================
async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    await q.message.reply_text("Send M-Pesa code:")
    return ENTER_CODE

async def receive_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    code = update.message.text

    users[uid]["mpesa_code"] = code
    save_users()

    await context.bot.send_message(
        ADMIN_ID,
        f"PAYMENT\nUSER: {uid}\nCODE: {code}\nPLAN: {users[uid].get('pending_plan')}"
    )

    await update.message.reply_text("Waiting approval...")
    return ConversationHandler.END

# ================= APPROVE =================
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Usage: /approve USER_ID")
        return

    uid = context.args[0]

    if uid not in users:
        await update.message.reply_text("User not found")
        return

    plan = users[uid].get("pending_plan", "basic")

    users[uid]["plan"] = plan
    users[uid]["expiry"] = (datetime.now() + timedelta(days=PLANS[plan])).isoformat()
    save_users()

    await context.bot.send_message(uid, f"✅ ACTIVATED {plan}")
    await update.message.reply_text("Done")

# ================= SIGNAL =================
async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    msg = update.message
    text = (msg.text or msg.caption or "") + "\n\n" + BRAND

    try:
        if msg.photo:
            await context.bot.send_photo(VIP_CHANNEL_ID, msg.photo[-1].file_id, caption=text)
        elif msg.video:
            await context.bot.send_video(VIP_CHANNEL_ID, msg.video.file_id, caption=text)
        else:
            await context.bot.send_message(VIP_CHANNEL_ID, text)
    except:
        pass

# ================= RUN =================
def run():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(confirm, pattern="confirm")],
        states={
            ENTER_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_code)]
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("approve", approve))

    app.add_handler(CallbackQueryHandler(menu, pattern="^(subscribe|status|payment|contact)$"))
    app.add_handler(CallbackQueryHandler(plan_select, pattern="^(trial|basic|vip)$"))

    app.add_handler(conv)

    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, signal))

    print("🔥 BOT RUNNING")
    app.run_polling()

if __name__ == "__main__":
    run()
