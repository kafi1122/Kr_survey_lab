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
    ["🆔 My ID"]
], resize_keyboard=True)

admin_kb = ReplyKeyboardMarkup([
    ["👥 Total Users", "💰 Paid Users"],
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

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""💰 Subscription Plans:

Weekly - 100৳
15 Days - 180৳
Monthly - 300৳

📲 Payment: Bkash / Nagad
Contact admin after payment.""")

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

    now = datetime.now()

    if user["week_start"]:
        week_start = datetime.fromisoformat(user["week_start"])
        if now - week_start < timedelta(days=7):
            if user["ip_count"] >= 2:
                await update.message.reply_text("Weekly IP limit reached!")
                return
        else:
            supabase.table("users").update({
                "ip_count": 0,
                "week_start": now.isoformat()
            }).eq("user_id", user_id).execute()
    else:
        supabase.table("users").update({
            "week_start": now.isoformat()
        }).eq("user_id", user_id).execute()

    ips = supabase.table("ips").select("*").execute().data

    selected_ip = None

    for ip_obj in ips:
        usage = supabase.table("ip_usage").select("*").eq("ip", ip_obj["ip"]).execute()
        if len(usage.data) < 3:
            selected_ip = ip_obj["ip"]
            break

    if not selected_ip:
        await update.message.reply_text("Ip not available right now contact your admin")
        return

    supabase.table("ip_usage").insert({
        "ip": selected_ip,
        "user_id": user_id
    }).execute()

    supabase.table("users").update({
        "current_ip": selected_ip,
        "ip_count": (user["ip_count"] or 0) + 1
    }).eq("user_id", user_id).execute()

    await update.message.reply_text(f"Your IP:\n{selected_ip}")

# ========= HANDLER =========
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    uid = update.effective_user.id

    # ===== STATE =====
    if uid in user_states:
        if user_states[uid] == "add_ip":
            supabase.table("ips").insert({"ip": text}).execute()
            await update.message.reply_text(f"IP Added: {text}", reply_markup=admin_kb)
            user_states.pop(uid)
            return

        elif user_states[uid] == "remove_ip":
            supabase.table("ips").delete().eq("ip", text).execute()
            await update.message.reply_text(f"IP Removed: {text}", reply_markup=admin_kb)
            user_states.pop(uid)
            return

    # ===== BUTTON MATCH =====
    if text.startswith("📦"):
        await myplan(update, context)

    elif text.startswith("🌐"):
        await getip(update, context)

    elif text.startswith("🔁"):
        await getip(update, context)

    elif text.startswith("💰") and "Buy" in text:
        await buy(update, context)

    elif text.startswith("🆔"):
        await myid(update, context)

    elif text.startswith("👥"):
        await total_users(update, context)

    elif text.startswith("💰") and "Paid" in text:
        await paid_users(update, context)

    elif text.startswith("📜"):
        await listip(update, context)

    elif text.startswith("➕"):
        user_states[uid] = "add_ip"
        await update.message.reply_text("Send IP (example: 1.1.1.1:8080)")

    elif text.startswith("➖"):
        user_states[uid] = "remove_ip"
        await update.message.reply_text("Send IP to remove")

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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))

    app.run_polling()
