from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from flask import Flask
import threading
import os
from datetime import datetime, timedelta
from supabase import create_client

# ========= CONFIG =========
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 2039785960

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ========= KEYBOARDS =========
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

    if data.data:
        if user.id == ADMIN_ID:
            await update.message.reply_text("Welcome Admin", reply_markup=admin_kb)
        else:
            await update.message.reply_text("Welcome back!", reply_markup=user_kb)
    else:
        supabase.table("users").insert({
            "user_id": user.id,
            "username": user.username,
            "plan": None,
            "expire_date": None,
            "week_start": None,
            "ip_count": 0,
            "current_ip": None
        }).execute()

        await update.message.reply_text("Registration successful!", reply_markup=user_kb)

# ========= USER =========
async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your ID: {update.effective_user.id}")

async def myplan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = supabase.table("users").select("*").eq("user_id", update.effective_user.id).execute()

    if not data.data:
        return

    user = data.data[0]

    if not user["plan"]:
        await update.message.reply_text("No active subscription!")
        return

    await update.message.reply_text(f"Plan: {user['plan']}\nExpire: {user['expire_date']}")

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""💰 Subscription Plans:

Weekly - 100৳
15 Days - 180৳
Monthly - 300৳

📲 Payment: Bkash / Nagad
After payment click '💸 I Paid'
""")

# ========= PAYMENT SYSTEM =========
async def mark_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    supabase.table("payments").insert({
        "user_id": user_id,
        "status": "pending"
    }).execute()

    await update.message.reply_text("✅ Payment request sent to admin")

    # notify admin
    await context.bot.send_message(
        ADMIN_ID,
        f"💸 New Payment Request\nUser ID: {user_id}"
    )

async def pending_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    data = supabase.table("payments").select("*").eq("status", "pending").execute()

    if not data.data:
        await update.message.reply_text("No pending payments")
        return

    text = "📥 Pending Users:\n"
    for p in data.data:
        text += f"{p['user_id']}\n"

    text += "\nType user ID to approve"

    await update.message.reply_text(text)

# ========= APPROVE =========
async def approve_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        uid = int(update.message.text)

        plans = """Select Plan:
/approve {uid} weekly
/approve {uid} 15days
/approve {uid} monthly""".replace("{uid}", str(uid))

        await update.message.reply_text(plans)

    except:
        await update.message.reply_text("Invalid ID")

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        uid = int(context.args[0])
        plan = context.args[1]

        days = {"weekly":7, "15days":15, "monthly":30}.get(plan)
        if not days:
            await update.message.reply_text("Invalid plan")
            return

        expire = datetime.now() + timedelta(days=days)

        supabase.table("users").update({
            "plan": plan,
            "expire_date": expire.isoformat()
        }).eq("user_id", uid).execute()

        supabase.table("payments").update({
            "status": "approved"
        }).eq("user_id", uid).execute()

        await update.message.reply_text("✅ Approved")

    except:
        await update.message.reply_text("Usage: /approve user_id plan")

# ========= ADMIN =========
async def total_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    data = supabase.table("users").select("*").execute()
    await update.message.reply_text(f"Total Users: {len(data.data)}")

async def paid_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    data = supabase.table("users").select("*").neq("plan", None).execute()
    await update.message.reply_text(f"Paid Users: {len(data.data)}")

# ========= IP =========
async def addip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        ip = context.args[0]
        supabase.table("ips").insert({"ip": ip}).execute()
        await update.message.reply_text(f"Added: {ip}")
    except:
        await update.message.reply_text("Usage: /addip ip:port")

async def removeip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        ip = context.args[0]
        supabase.table("ips").delete().eq("ip", ip).execute()
        await update.message.reply_text(f"Removed: {ip}")
    except:
        await update.message.reply_text("Usage: /removeip ip")

async def listip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = supabase.table("ips").select("*").execute()
    ips = [i["ip"] for i in data.data]

    await update.message.reply_text("\n".join(ips) if ips else "No IP")

# ========= BUTTON HANDLER =========
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📦 My Plan":
        await myplan(update, context)

    elif text == "🌐 Get IP" or text == "🔁 Change IP":
        await update.message.reply_text("IP system working")

    elif text == "💰 Buy Plan":
        await buy(update, context)

    elif text == "💸 I Paid":
        await mark_paid(update, context)

    elif text == "🆔 My ID":
        await myid(update, context)

    elif text == "👥 Total Users":
        await total_users(update, context)

    elif text == "💰 Paid Users":
        await paid_users(update, context)

    elif text == "📥 Pending Payments":
        await pending_payments(update, context)

    elif text == "➕ Add IP":
        await update.message.reply_text("Use: /addip ip:port")

    elif text == "➖ Remove IP":
        await update.message.reply_text("Use: /removeip ip")

    elif text == "📜 IP List":
        await listip(update, context)

    else:
        # admin enters user id for approval
        if update.effective_user.id == ADMIN_ID:
            await approve_user(update, context)

# ========= FLASK =========
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is alive!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port, use_reloader=False)

# ========= RUN =========
if __name__ == "__main__":
    threading.Thread(target=run_web).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("addip", addip))
    app.add_handler(CommandHandler("removeip", removeip))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))

    app.run_polling()
