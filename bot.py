from telegram import (
    Update, ReplyKeyboardMarkup,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
import os
from datetime import datetime, timedelta
from supabase import create_client

# ========= CONFIG =========
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 2039785960

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ========= KEYBOARD =========
user_kb = ReplyKeyboardMarkup([
    ["📦 My Plan", "🌐 Get IP"],
    ["🔁 Change IP", "💰 Buy Plan"],
    ["💸 I Paid", "🆔 My ID"]
], resize_keyboard=True)

admin_kb = ReplyKeyboardMarkup([
    ["👥 Total Users", "💰 Paid Users"],
    ["📥 Pending Payments"],
    ["➕ Add IP", "➖ Remove IP"],
    ["📜 IP List"]
], resize_keyboard=True)

# ========= START =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    data = supabase.table("users").select("*").eq("user_id", user.id).execute()

    if not data.data:
        supabase.table("users").insert({
            "user_id": user.id,
            "username": user.username,
            "plan": None,
            "expire_date": None,
            "week_start": None,
            "ip_count": 0,
            "current_ip": None
        }).execute()

    if user.id == ADMIN_ID:
        await update.message.reply_text("Admin Panel", reply_markup=admin_kb)
    else:
        await update.message.reply_text("User Panel", reply_markup=user_kb)

# ========= USER =========
async def myplan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = supabase.table("users").select("*").eq("user_id", update.effective_user.id).execute().data[0]

    if not user["plan"]:
        await update.message.reply_text("No active subscription!")
        return

    await update.message.reply_text(
        f"Plan: {user['plan']}\nExpire: {user['expire_date']}"
    )

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""💰 Plans:

Weekly - 100৳
15 Days - 180৳
Monthly - 300৳

After payment press 💸 I Paid
""")

async def mark_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    supabase.table("payments").insert({
        "user_id": uid,
        "status": "pending"
    }).execute()

    await update.message.reply_text("✅ Payment submitted")

# ========= ADMIN =========
async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    data = supabase.table("payments").select("*").eq("status", "pending").execute()

    if not data.data:
        await update.message.reply_text("No pending payments")
        return

    for p in data.data:
        uid = p["user_id"]

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Weekly", callback_data=f"approve|{uid}|weekly"),
                InlineKeyboardButton("✅ 15 Days", callback_data=f"approve|{uid}|15days"),
            ],
            [
                InlineKeyboardButton("✅ Monthly", callback_data=f"approve|{uid}|monthly"),
            ],
            [
                InlineKeyboardButton("❌ Reject", callback_data=f"reject|{uid}")
            ]
        ])

        await update.message.reply_text(
            f"💳 Payment from User:\nID: {uid}",
            reply_markup=keyboard
        )

# ========= CALLBACK =========
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split("|")

    action = data[0]
    uid = int(data[1])

    if action == "approve":
        plan = data[2]

        days = {
            "weekly": 7,
            "15days": 15,
            "monthly": 30
        }[plan]

        expire = datetime.now() + timedelta(days=days)

        supabase.table("users").update({
            "plan": plan,
            "expire_date": expire.isoformat(),
            "ip_count": 0,
            "week_start": datetime.now().isoformat()
        }).eq("user_id", uid).execute()

        supabase.table("payments").update({
            "status": "approved"
        }).eq("user_id", uid).execute()

        await query.edit_message_text(f"✅ Approved {plan} for {uid}")

    elif action == "reject":
        supabase.table("payments").update({
            "status": "rejected"
        }).eq("user_id", uid).execute()

        await query.edit_message_text(f"❌ Rejected payment for {uid}")

# ========= HANDLER =========
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📦 My Plan":
        await myplan(update, context)

    elif text in ["🌐 Get IP", "🔁 Change IP"]:
        await update.message.reply_text("IP system working...")

    elif text == "💰 Buy Plan":
        await buy(update, context)

    elif text == "💸 I Paid":
        await mark_paid(update, context)

    elif text == "🆔 My ID":
        await update.message.reply_text(str(update.effective_user.id))

    elif text == "📥 Pending Payments":
        await pending(update, context)

    elif text == "👥 Total Users":
        data = supabase.table("users").select("*").execute()
        await update.message.reply_text(f"Total Users: {len(data.data)}")

    elif text == "💰 Paid Users":
        data = supabase.table("users").select("*").neq("plan", None).execute()
        await update.message.reply_text(f"Paid Users: {len(data.data)}")

    else:
        await update.message.reply_text("Use menu buttons")

# ========= RUN =========
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_handler(CallbackQueryHandler(callback_handler))

    print("Bot running...")
    app.run_polling()
