from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
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

user_state = {}

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
            "ip_count": 0
        }).execute()

    if user.id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("📥 Pending Payments", callback_data="payments")],
            [InlineKeyboardButton("👥 Total Users", callback_data="users")],
            [InlineKeyboardButton("➕ Add IP", callback_data="addip"),
             InlineKeyboardButton("➖ Remove IP", callback_data="removeip")],
            [InlineKeyboardButton("📜 IP List", callback_data="iplist")]
        ]
        await update.message.reply_text("Admin Panel", reply_markup=InlineKeyboardMarkup(keyboard))

    else:
        keyboard = [
            [InlineKeyboardButton("📦 My Plan", callback_data="myplan"),
             InlineKeyboardButton("🌐 Get IP", callback_data="getip")],
            [InlineKeyboardButton("🔁 Change IP", callback_data="getip")],
            [InlineKeyboardButton("💰 Buy Plan", callback_data="buy")],
            [InlineKeyboardButton("💸 I Paid", callback_data="paid")]
        ]
        await update.message.reply_text("User Menu", reply_markup=InlineKeyboardMarkup(keyboard))

# ========= CALLBACK =========
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    data = query.data

    # ===== USER =====
    if data == "paid":
        if uid == ADMIN_ID:
            return  # admin can't pay

        # prevent duplicate pending
        existing = supabase.table("payments").select("*").eq("user_id", uid).eq("status", "pending").execute()

        if existing.data:
            await query.message.reply_text("Already requested")
            return

        supabase.table("payments").insert({
            "user_id": uid,
            "status": "pending"
        }).execute()

        # send to admin with approve + reject
        keyboard = [[
            InlineKeyboardButton("✅ Weekly", callback_data=f"approve_{uid}_weekly"),
            InlineKeyboardButton("✅ 15 Days", callback_data=f"approve_{uid}_15days"),
            InlineKeyboardButton("✅ Monthly", callback_data=f"approve_{uid}_monthly")
        ],
        [
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}")
        ]]

        await context.bot.send_message(
            ADMIN_ID,
            f"💸 Payment Request\nUser: {uid}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        await query.message.reply_text("Payment sent to admin")

    elif data == "buy":
        await query.message.reply_text("Weekly=100৳\n15days=180৳\nMonthly=300৳")

    elif data == "myplan":
        user = supabase.table("users").select("*").eq("user_id", uid).execute().data[0]

        if not user["plan"]:
            await query.message.reply_text("No active plan")
        else:
            await query.message.reply_text(f"{user['plan']} | {user['expire_date']}")

    elif data == "getip":
        user = supabase.table("users").select("*").eq("user_id", uid).execute().data[0]

        if not user["plan"]:
            await query.message.reply_text("No plan")
            return

        if user["ip_count"] >= 2:
            await query.message.reply_text("Already full your IP quota")
            return

        ips = supabase.table("ips").select("*").execute().data

        for ip in ips:
            usage = supabase.table("ip_usage").select("*").eq("ip", ip["ip"]).execute()
            if len(usage.data) < 3:
                supabase.table("ip_usage").insert({"ip": ip["ip"], "user_id": uid}).execute()

                supabase.table("users").update({
                    "ip_count": user["ip_count"] + 1
                }).eq("user_id", uid).execute()

                await query.message.reply_text(ip["ip"])
                return

        await query.message.reply_text("IP not available")

    # ===== ADMIN =====
    elif data == "payments":
        if uid != ADMIN_ID:
            return

        data_p = supabase.table("payments").select("*").eq("status", "pending").execute().data

        if not data_p:
            await query.message.reply_text("No pending payments")
        else:
            txt = "\n".join([str(p["user_id"]) for p in data_p if p["user_id"] != ADMIN_ID])
            await query.message.reply_text(f"Pending Users:\n{txt}")

    elif data.startswith("approve"):
        if uid != ADMIN_ID:
            return

        _, user_id, plan = data.split("_")

        days_map = {"weekly":7, "15days":15, "monthly":30}
        expire = datetime.now() + timedelta(days=days_map[plan])

        supabase.table("users").update({
            "plan": plan,
            "expire_date": expire.isoformat(),
            "ip_count": 0
        }).eq("user_id", int(user_id)).execute()

        supabase.table("payments").update({
            "status": "approved"
        }).eq("user_id", int(user_id)).execute()

        await query.message.reply_text(f"Approved {user_id}")

    elif data.startswith("reject"):
        if uid != ADMIN_ID:
            return

        _, user_id = data.split("_")

        supabase.table("payments").update({
            "status": "rejected"
        }).eq("user_id", int(user_id)).execute()

        await query.message.reply_text(f"Rejected {user_id}")

    elif data == "users":
        if uid != ADMIN_ID:
            return

        count = len(supabase.table("users").select("*").execute().data)
        await query.message.reply_text(f"Total Users: {count}")

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
    app.add_handler(CallbackQueryHandler(button))

    app.run_polling()
