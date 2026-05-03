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
    ["💸 I Paid", "🔄 Refresh"],
    ["🆔 My ID"]
], resize_keyboard=True)

admin_kb = ReplyKeyboardMarkup([
    ["👥 Total Users", "💰 Paid Users"],
    ["📥 Pending Payments", "❌ Terminate User"],
    ["➕ Add IP", "➖ Remove IP"],
    ["📜 IP List", "🔄 Refresh"]
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
        await update.message.reply_text("Welcome!", reply_markup=user_kb)

# ========= BASIC =========
async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your ID: {update.effective_user.id}")

async def myplan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = supabase.table("users").select("*").eq("user_id", update.effective_user.id).execute()
    user = data.data[0]

    if not user["plan"]:
        await update.message.reply_text("No active subscription!")
        return

    await update.message.reply_text(f"Plan: {user['plan']}\nExpire: {user['expire_date']}")

# ========= PAYMENT =========
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""💰 Plans:

Weekly - 100৳
15 Days - 180৳
Monthly - 300৳

After payment press '💸 I Paid'
""")

async def mark_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    supabase.table("payments").insert({
        "user_id": uid,
        "status": "pending"
    }).execute()

    await update.message.reply_text("Payment request sent!")

    await context.bot.send_message(ADMIN_ID, f"💸 New Payment\nUser: {uid}")

# ========= ADMIN =========
async def total_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = supabase.table("users").select("*").execute()
    await update.message.reply_text(f"Total Users: {len(data.data)}")

async def paid_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = supabase.table("users").select("*").neq("plan", None).execute()
    await update.message.reply_text(f"Paid Users: {len(data.data)}")

async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = supabase.table("payments").select("*").eq("status", "pending").execute()

    if not data.data:
        await update.message.reply_text("No pending payments")
        return

    text = "Pending Users:\n"
    for p in data.data:
        text += f"{p['user_id']}\n"

    await update.message.reply_text(text)

# ========= APPROVE =========
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(context.args[0])
        plan = context.args[1]

        days = {"weekly":7, "15days":15, "monthly":30}[plan]

        expire = datetime.now() + timedelta(days=days)

        supabase.table("users").update({
            "plan": plan,
            "expire_date": expire.isoformat(),
            "ip_count": 0,
            "week_start": datetime.now().isoformat()
        }).eq("user_id", uid).execute()

        supabase.table("payments").update({"status":"approved"}).eq("user_id", uid).execute()

        await update.message.reply_text("Approved!")

    except:
        await update.message.reply_text("Usage: /approve user_id weekly")

# ========= TERMINATE =========
async def terminate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(context.args[0])

        supabase.table("users").update({
            "plan": None,
            "expire_date": None
        }).eq("user_id", uid).execute()

        await update.message.reply_text("User terminated")

    except:
        await update.message.reply_text("Usage: /terminate user_id")

# ========= IP SYSTEM =========
async def getip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = supabase.table("users").select("*").eq("user_id", uid).execute().data[0]

    if not user["plan"]:
        await update.message.reply_text("No active subscription!")
        return

    if datetime.now() > datetime.fromisoformat(user["expire_date"]):
        await update.message.reply_text("Expired!")
        return

    now = datetime.now()

    if user["week_start"]:
        week = datetime.fromisoformat(user["week_start"])
        if now - week < timedelta(days=7):
            if user["ip_count"] >= 2:
                await update.message.reply_text("Already full your IP quota")
                return
        else:
            supabase.table("users").update({
                "ip_count": 0,
                "week_start": now.isoformat()
            }).eq("user_id", uid).execute()

    ips = supabase.table("ips").select("*").execute().data

    selected = None

    for ip in ips:
        usage = supabase.table("ip_usage").select("*").eq("ip", ip["ip"]).execute()
        if len(usage.data) < 3:
            selected = ip["ip"]
            break

    if not selected:
        await update.message.reply_text("Ip not available right now contact admin")
        return

    supabase.table("ip_usage").insert({"ip": selected, "user_id": uid}).execute()

    supabase.table("users").update({
        "current_ip": selected,
        "ip_count": (user["ip_count"] or 0) + 1
    }).eq("user_id", uid).execute()

    await update.message.reply_text(selected)

# ========= HANDLER =========
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text

    if t == "📦 My Plan":
        await myplan(update, context)

    elif t in ["🌐 Get IP", "🔁 Change IP"]:
        await getip(update, context)

    elif t == "💰 Buy Plan":
        await buy(update, context)

    elif t == "💸 I Paid":
        await mark_paid(update, context)

    elif t == "🆔 My ID":
        await myid(update, context)

    elif t == "👥 Total Users":
        await total_users(update, context)

    elif t == "💰 Paid Users":
        await paid_users(update, context)

    elif t == "📥 Pending Payments":
        await pending(update, context)

    elif t == "📜 IP List":
        await listip(update, context)

    elif t == "🔄 Refresh":
        await start(update, context)

# ========= FLASK =========
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot alive"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port, use_reloader=False)

# ========= RUN =========
if __name__ == "__main__":
    threading.Thread(target=run_web).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("terminate", terminate))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    app.run_polling()
