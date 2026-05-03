from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler
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

# ========= STATE =========
user_states = {}

# ========= KEYBOARDS =========
user_kb = ReplyKeyboardMarkup([
    ["📦 My Plan", "🌐 Get IP"],
    ["🔁 Change IP", "💰 Buy Plan"],
    ["🆔 My ID", "💸 I Paid"]
], resize_keyboard=True)

admin_kb = ReplyKeyboardMarkup([
    ["👥 Total Users", "💰 Paid Users"],
    ["➕ Add IP", "➖ Remove IP"],
    ["📜 IP List", "📥 Pending Payments"]
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

# ========= BASIC =========
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

# ========= BUY =========
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""💰 Subscription Plans:

Weekly - 100৳
15 Days - 180৳
Monthly - 300৳

📲 Payment: Bkash / Nagad

After payment press 💸 I Paid""")

# ========= PAYMENT =========
async def mark_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # add to pending table
    supabase.table("payments").insert({
        "user_id": user.id,
        "username": user.username
    }).execute()

    await update.message.reply_text("Payment request sent to admin!")

    # notify admin
    try:
        await context.bot.send_message(
            ADMIN_ID,
            f"💸 New Payment Request\nUser ID: {user.id}"
        )
    except:
        pass

async def pending_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = supabase.table("payments").select("*").execute()

    if not data.data:
        await update.message.reply_text("No pending payments")
        return

    text = "📥 Pending Users:\n"
    for u in data.data:
        text += f"{u['user_id']}\n"

    text += "\nUse: /approve user_id plan"

    await update.message.reply_text(text)

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        uid = int(context.args[0])
        plan = context.args[1]

        days = {"weekly":7, "15days":15, "monthly":30}.get(plan)

        expire = datetime.now() + timedelta(days=days)

        supabase.table("users").update({
            "plan": plan,
            "expire_date": expire.isoformat()
        }).eq("user_id", uid).execute()

        # remove from pending
        supabase.table("payments").delete().eq("user_id", uid).execute()

        await update.message.reply_text(f"Approved {uid} → {plan}")

    except:
        await update.message.reply_text("Usage: /approve user_id plan")

# ========= ADMIN =========
async def total_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = supabase.table("users").select("*").execute()
    await update.message.reply_text(f"Total Users: {len(data.data)}", reply_markup=admin_kb)

async def paid_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = supabase.table("users").select("*").neq("plan", None).execute()
    await update.message.reply_text(f"Paid Users: {len(data.data)}", reply_markup=admin_kb)

# ========= IP =========
async def listip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = supabase.table("ips").select("*").execute()
    ips = [i["ip"] for i in data.data]
    await update.message.reply_text("\n".join(ips) if ips else "No IP")

async def getip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    data = supabase.table("users").select("*").eq("user_id", user_id).execute()
    if not data.data:
        return

    user = data.data[0]

    if not user["plan"]:
        await update.message.reply_text("No active subscription!")
        return

    if datetime.now() > datetime.fromisoformat(user["expire_date"]):
        await update.message.reply_text("Subscription expired!")
        return

    ips = supabase.table("ips").select("*").execute().data

    for ip_obj in ips:
        usage = supabase.table("ip_usage").select("*").eq("ip", ip_obj["ip"]).execute()
        if len(usage.data) < 3:
            supabase.table("ip_usage").insert({
                "ip": ip_obj["ip"],
                "user_id": user_id
            }).execute()

            await update.message.reply_text(f"Your IP:\n{ip_obj['ip']}")
            return

    await update.message.reply_text("Ip not available right now contact your admin")

# ========= HANDLER =========
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text.startswith("📦"):
        await myplan(update, context)

    elif text.startswith("🌐"):
        await getip(update, context)

    elif text.startswith("🔁"):
        await getip(update, context)

    elif text.startswith("💰") and "Buy" in text:
        await buy(update, context)

    elif text.startswith("💸"):
        await mark_paid(update, context)

    elif text.startswith("🆔"):
        await myid(update, context)

    elif text.startswith("👥"):
        await total_users(update, context)

    elif text.startswith("💰") and "Paid" in text:
        await paid_users(update, context)

    elif text.startswith("📜"):
        await listip(update, context)

    elif text.startswith("📥"):
        await pending_payments(update, context)

    else:
        await update.message.reply_text("Invalid option")

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

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))

    app.run_polling()
