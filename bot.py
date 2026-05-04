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

# ========= FLASK =========
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is running!"

# ========= KEYBOARDS =========
user_kb = ReplyKeyboardMarkup([
    ["📦 My Plan", "🌐 Get IP"],
    ["🔁 Change IP", "💰 Buy Plan"],
    ["💸 I Paid", "🔄 Refresh"],
    ["🆔 My ID"]
], resize_keyboard=True)

admin_kb = ReplyKeyboardMarkup([
    ["👥 Total Users", "💰 Paid Users"],
    ["📥 Pending Payments"],
    ["➕ Add IP", "➖ Remove IP"],
    ["📜 IP List", "❌ Terminate User"],
    ["🔄 Refresh"]
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

# ========= PAYMENT =========
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💰 Plans:\n\nWeekly\n15 Days\nMonthly\n\nAfter payment click '💸 I Paid'"
    )

async def mark_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    supabase.table("payments").insert({
        "user_id": uid,
        "status": "pending"
    }).execute()

    await update.message.reply_text("Payment sent to admin")

    await context.bot.send_message(
        ADMIN_ID,
        f"💸 Payment from {uid}",
        reply_markup=ReplyKeyboardMarkup([
            [f"✅ Weekly {uid}"],
            [f"✅ 15days {uid}"],
            [f"✅ Monthly {uid}"],
            [f"❌ Reject {uid}"]
        ], resize_keyboard=True)
    )

# ========= APPROVE =========
async def approve(uid, plan):
    days = {"weekly": 7, "15days": 15, "monthly": 30}[plan]
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
                await update.message.reply_text("Already full your Ip quota")
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

# ========= MAIN HANDLER =========
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # USER
    if text == "📦 My Plan":
        user = supabase.table("users").select("*").eq("user_id", update.effective_user.id).execute().data[0]

        if not user["plan"]:
            await update.message.reply_text("No active subscription!")
        else:
            await update.message.reply_text(f"{user['plan']} until {user['expire_date']}")

    elif text in ["🌐 Get IP", "🔁 Change IP"]:
        await getip(update, context)

    elif text == "💰 Buy Plan":
        await buy(update, context)

    elif text == "💸 I Paid":
        await mark_paid(update, context)

    elif text == "🆔 My ID":
        await update.message.reply_text(str(update.effective_user.id))

    elif text == "🔄 Refresh":
        await start(update, context)

    # ADMIN
    elif text.startswith("✅"):
        parts = text.split()
        plan = parts[1].lower()
        uid = int(parts[2])

        await approve(uid, plan)
        await update.message.reply_text("Approved!")

    elif text.startswith("❌ Reject"):
        uid = int(text.split()[2])
        supabase.table("payments").update({"status": "rejected"}).eq("user_id", uid).execute()
        await update.message.reply_text("Rejected")

    elif text == "👥 Total Users":
        data = supabase.table("users").select("*").execute()
        await update.message.reply_text(f"Total: {len(data.data)}")

    elif text == "💰 Paid Users":
        data = supabase.table("users").select("*").neq("plan", None).execute()
        await update.message.reply_text(f"Paid: {len(data.data)}")

    elif text == "📜 IP List":
        data = supabase.table("ips").select("*").execute()
        txt = "\n\n".join([i["ip"] for i in data.data])
        await update.message.reply_text(txt or "No IP")

    elif text == "➕ Add IP":
        context.user_data["add"] = True
        await update.message.reply_text("Send IP text")

    elif context.user_data.get("add"):
        supabase.table("ips").insert({"ip": text}).execute()
        context.user_data["add"] = False
        await update.message.reply_text("IP Added")

    elif text == "➖ Remove IP":
        context.user_data["remove"] = True
        await update.message.reply_text("Send IP to remove")

    elif context.user_data.get("remove"):
        supabase.table("ips").delete().eq("ip", text).execute()
        context.user_data["remove"] = False
        await update.message.reply_text("Removed")

    elif text == "❌ Terminate User":
        context.user_data["terminate"] = True
        await update.message.reply_text("Send user ID")

    elif context.user_data.get("terminate"):
        try:
            uid = int(text)
            supabase.table("users").update({
                "plan": None,
                "expire_date": None
            }).eq("user_id", uid).execute()

            context.user_data["terminate"] = False
            await update.message.reply_text("User terminated")
        except:
            await update.message.reply_text("Invalid ID")

# ========= BOT THREAD =========
def run_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    app.run_polling()

# ========= MAIN =========
if __name__ == "__main__":
    threading.Thread(target=run_bot).start()

    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port)
