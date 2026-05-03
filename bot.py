from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
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
user_state = {}

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

# ========= PAYMENT =========
async def mark_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    supabase.table("payments").insert({
        "user_id": uid,
        "status": "pending"
    }).execute()

    await update.message.reply_text("Payment request sent!")

# ========= ADMIN =========
async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = supabase.table("payments").select("*").eq("status", "pending").execute()

    if not data.data:
        await update.message.reply_text("No pending payments")
        return

    for p in data.data:
        uid = p["user_id"]

        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("Weekly", callback_data=f"approve_{uid}_weekly")],
            [InlineKeyboardButton("15 Days", callback_data=f"approve_{uid}_15days")],
            [InlineKeyboardButton("Monthly", callback_data=f"approve_{uid}_monthly")]
        ])

        await update.message.reply_text(f"User: {uid}", reply_markup=buttons)

# ========= CALLBACK =========
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("approve_"):
        _, uid, plan = data.split("_")

        uid = int(uid)
        days = {"weekly":7, "15days":15, "monthly":30}[plan]

        expire = datetime.now() + timedelta(days=days)

        supabase.table("users").update({
            "plan": plan,
            "expire_date": expire.isoformat(),
            "ip_count": 0,
            "week_start": datetime.now().isoformat()
        }).eq("user_id", uid).execute()

        supabase.table("payments").update({
            "status":"approved"
        }).eq("user_id", uid).execute()

        await query.edit_message_text(f"Approved {uid} ({plan})")

# ========= IP =========
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
    uid = update.effective_user.id
    text = update.message.text

    # STATE BASED
    if uid in user_state:
        mode = user_state[uid]

        if mode == "add_ip":
            supabase.table("ips").insert({"ip": text}).execute()
            await update.message.reply_text("IP Added")
            user_state.pop(uid)
            return

        if mode == "remove_ip":
            supabase.table("ips").delete().eq("ip", text).execute()
            await update.message.reply_text("IP Removed")
            user_state.pop(uid)
            return

        if mode == "terminate":
            supabase.table("users").update({
                "plan": None,
                "expire_date": None
            }).eq("user_id", int(text)).execute()

            await update.message.reply_text("User Terminated")
            user_state.pop(uid)
            return

    # BUTTONS
    if text == "🌐 Get IP" or text == "🔁 Change IP":
        await getip(update, context)

    elif text == "💸 I Paid":
        await mark_paid(update, context)

    elif text == "📥 Pending Payments":
        await pending(update, context)

    elif text == "➕ Add IP":
        user_state[uid] = "add_ip"
        await update.message.reply_text("Send IP text")

    elif text == "➖ Remove IP":
        user_state[uid] = "remove_ip"
        await update.message.reply_text("Send IP to remove")

    elif text == "❌ Terminate User":
        user_state[uid] = "terminate"
        await update.message.reply_text("Send user ID")

    elif text == "🔄 Refresh":
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
    app.add_handler(CallbackQueryHandler(button_callback))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    app.run_polling()
