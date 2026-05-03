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

# ========= STATE =========
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
            [InlineKeyboardButton("👥 Users", callback_data="users"),
             InlineKeyboardButton("💰 Paid", callback_data="paid")],
            [InlineKeyboardButton("📥 Payments", callback_data="payments")],
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
    if data == "myplan":
        user = supabase.table("users").select("*").eq("user_id", uid).execute().data[0]

        if not user["plan"]:
            await query.message.reply_text("No active plan")
        else:
            await query.message.reply_text(f"{user['plan']} | {user['expire_date']}")

    elif data == "buy":
        await query.message.reply_text("Weekly=100৳\n15days=180৳\nMonthly=300৳\nAfter payment press I Paid")

    elif data == "paid":
        supabase.table("payments").insert({"user_id": uid, "status": "pending"}).execute()

        # send approve button to admin
        keyboard = [
            [
                InlineKeyboardButton("Approve Weekly", callback_data=f"approve_{uid}_weekly"),
                InlineKeyboardButton("Approve 15Days", callback_data=f"approve_{uid}_15days"),
                InlineKeyboardButton("Approve Monthly", callback_data=f"approve_{uid}_monthly")
            ]
        ]

        await context.bot.send_message(
            ADMIN_ID,
            f"Payment from {uid}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        await query.message.reply_text("Payment sent to admin")

    elif data == "getip":
        user = supabase.table("users").select("*").eq("user_id", uid).execute().data[0]

        if not user["plan"]:
            await query.message.reply_text("No plan")
            return

        if user["ip_count"] >= 2:
            await query.message.reply_text("IP limit reached")
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

        await query.message.reply_text("No IP available")

    # ===== ADMIN =====
    elif data == "users":
        count = len(supabase.table("users").select("*").execute().data)
        await query.message.reply_text(f"Users: {count}")

    elif data == "paid":
        count = len(supabase.table("users").select("*").neq("plan", None).execute().data)
        await query.message.reply_text(f"Paid: {count}")

    elif data == "payments":
        data_p = supabase.table("payments").select("*").eq("status", "pending").execute().data

        if not data_p:
            await query.message.reply_text("No pending payments")
        else:
            txt = "\n".join([str(p["user_id"]) for p in data_p])
            await query.message.reply_text(f"Pending:\n{txt}")

    elif data == "addip":
        user_state[uid] = "addip"
        await query.message.reply_text("Send IP text")

    elif data == "removeip":
        user_state[uid] = "removeip"
        await query.message.reply_text("Send IP to remove")

    elif data == "iplist":
        ips = supabase.table("ips").select("*").execute().data
        txt = "\n\n".join([i["ip"] for i in ips])
        await query.message.reply_text(txt if txt else "No IP")

    # ===== APPROVE =====
    elif data.startswith("approve"):
        _, user_id, plan = data.split("_")

        days = {"weekly":7, "15days":15, "monthly":30}[plan]
        expire = datetime.now() + timedelta(days=days)

        supabase.table("users").update({
            "plan": plan,
            "expire_date": expire.isoformat(),
            "ip_count": 0
        }).eq("user_id", int(user_id)).execute()

        supabase.table("payments").update({
            "status": "approved"
        }).eq("user_id", int(user_id)).execute()

        await query.message.reply_text(f"Approved {user_id}")

# ========= TEXT HANDLER =========
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    state = user_state.get(uid)

    if state == "addip":
        supabase.table("ips").insert({"ip": text}).execute()
        user_state.pop(uid)
        await update.message.reply_text("IP added")

    elif state == "removeip":
        supabase.table("ips").delete().eq("ip", text).execute()
        user_state.pop(uid)
        await update.message.reply_text("IP removed")

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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    app.run_polling()
