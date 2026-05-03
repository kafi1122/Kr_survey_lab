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
    ["💸 I Paid"],
    ["🆔 My ID"]
], resize_keyboard=True)

admin_kb = ReplyKeyboardMarkup([
    ["👥 Users", "💰 Paid"],
    ["📥 Payments", "❌ Terminate"],
    ["➕ Add IP", "➖ Remove IP"],
    ["📜 IP List"]
], resize_keyboard=True)

# ========= START =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # user create if not exists
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
        await update.message.reply_text("⚙️ Admin Panel", reply_markup=admin_kb)
    else:
        await update.message.reply_text("🚀 Welcome", reply_markup=user_kb)

# ========= USER =========
async def myplan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = supabase.table("users").select("*").eq("user_id", update.effective_user.id).execute().data[0]

    if not user["plan"]:
        await update.message.reply_text("No active subscription")
        return

    await update.message.reply_text(f"{user['plan']} | Expire: {user['expire_date']}")

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(str(update.effective_user.id))

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Weekly - 100৳\n15 Days - 180৳\nMonthly - 300৳\n\nAfter payment press 'I Paid'"
    )

async def paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    supabase.table("payments").insert({
        "user_id": uid,
        "status": "pending"
    }).execute()

    await update.message.reply_text("Request sent")

# ========= ADMIN =========
async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = supabase.table("users").select("*").execute()
    await update.message.reply_text(f"Users: {len(data.data)}")

async def paid_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = supabase.table("users").select("*").neq("plan", None).execute()
    await update.message.reply_text(f"Paid: {len(data.data)}")

async def payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = supabase.table("payments").select("*").eq("status", "pending").execute()

    if not data.data:
        await update.message.reply_text("No pending")
        return

    text = "Pending:\n"
    for p in data.data:
        text += f"{p['user_id']}\n"

    await update.message.reply_text(text)

# ========= IP =========
async def getip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = supabase.table("users").select("*").eq("user_id", uid).execute().data[0]

    if not user["plan"]:
        await update.message.reply_text("No plan")
        return

    if datetime.now() > datetime.fromisoformat(user["expire_date"]):
        await update.message.reply_text("Expired")
        return

    if user["ip_count"] >= 2:
        await update.message.reply_text("IP limit reached")
        return

    ips = supabase.table("ips").select("*").execute().data

    for ip in ips:
        usage = supabase.table("ip_usage").select("*").eq("ip", ip["ip"]).execute()

        if len(usage.data) < 3:
            supabase.table("ip_usage").insert({"ip": ip["ip"], "user_id": uid}).execute()

            supabase.table("users").update({
                "ip_count": user["ip_count"] + 1
            }).eq("user_id", uid).execute()

            await update.message.reply_text(ip["ip"])
            return

    await update.message.reply_text("No IP available")

# ========= HANDLER =========
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📦 My Plan":
        await myplan(update, context)

    elif text == "🌐 Get IP" or text == "🔁 Change IP":
        await getip(update, context)

    elif text == "💰 Buy Plan":
        await buy(update, context)

    elif text == "💸 I Paid":
        await paid(update, context)

    elif text == "🆔 My ID":
        await myid(update, context)

    elif text == "👥 Users":
        await users(update, context)

    elif text == "💰 Paid":
        await paid_users(update, context)

    elif text == "📥 Payments":
        await payments(update, context)

# ========= FLASK =========
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Alive"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port)

# ========= RUN =========
if __name__ == "__main__":
    threading.Thread(target=run_web).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    app.run_polling()
