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

# ========= STATE =========
admin_state = {}

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
    user = supabase.table("users").select("*").eq("user_id", update.effective_user.id).execute().data[0]

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

    text += "\nSend User ID to approve"
    admin_state[update.effective_user.id] = "waiting_user_id"

    await update.message.reply_text(text)

# ========= APPROVE FLOW =========
async def approve_user(uid, plan):
    days_map = {"weekly":7, "15days":15, "monthly":30}

    expire = datetime.now() + timedelta(days=days_map[plan])

    supabase.table("users").update({
        "plan": plan,
        "expire_date": expire.isoformat(),
        "ip_count": 0,
        "week_start": datetime.now().isoformat()
    }).eq("user_id", uid).execute()

    supabase.table("payments").update({
        "status": "approved"
    }).eq("user_id", uid).execute()

# ========= TERMINATE =========
async def terminate_user(uid):
    supabase.table("users").update({
        "plan": None,
        "expire_date": None
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

    # weekly limit
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
            }).execute()

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

    supabase.table("ip_usage").insert({
        "ip": selected,
        "user_id": uid
    }).execute()

    supabase.table("users").update({
        "current_ip": selected,
        "ip_count": (user["ip_count"] or 0) + 1
    }).eq("user_id", uid).execute()

    await update.message.reply_text(selected)

# ========= HANDLER =========
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    # ===== ADMIN STATE FLOW =====
    if uid == ADMIN_ID:
        state = admin_state.get(uid)

        if state == "waiting_user_id":
            admin_state[uid] = {"user_id": int(text), "step": "choose_plan"}
            await update.message.reply_text("Choose Plan: weekly / 15days / monthly")
            return

        elif isinstance(state, dict) and state.get("step") == "choose_plan":
            await approve_user(state["user_id"], text)
            admin_state.pop(uid)
            await update.message.reply_text("Approved!")
            return

    # ===== BUTTONS =====
    if text == "📦 My Plan":
        await myplan(update, context)

    elif text in ["🌐 Get IP", "🔁 Change IP"]:
        await getip(update, context)

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
        await pending(update, context)

    elif text == "📜 IP List":
        data = supabase.table("ips").select("*").execute()
        txt = "\n\n".join([i["ip"] for i in data.data])
        await update.message.reply_text(txt if txt else "No IP")

    elif text == "➕ Add IP":
        admin_state[uid] = "add_ip"
        await update.message.reply_text("Send full IP text")
        return

    elif text == "➖ Remove IP":
        admin_state[uid] = "remove_ip"
        await update.message.reply_text("Send IP to remove")
        return

    elif text == "❌ Terminate User":
        admin_state[uid] = "terminate"
        await update.message.reply_text("Send User ID")
        return

    elif text == "🔄 Refresh":
        await start(update, context)

    # ===== STATE ACTIONS =====
    elif uid == ADMIN_ID:
        state = admin_state.get(uid)

        if state == "add_ip":
            supabase.table("ips").insert({"ip": text}).execute()
            admin_state.pop(uid)
            await update.message.reply_text("IP Added")

        elif state == "remove_ip":
            supabase.table("ips").delete().eq("ip", text).execute()
            admin_state.pop(uid)
            await update.message.reply_text("IP Removed")

        elif state == "terminate":
            await terminate_user(int(text))
            admin_state.pop(uid)
            await update.message.reply_text("User Terminated")

# ========= FLASK =========
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot Alive"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port, use_reloader=False)

# ========= RUN =========
if __name__ == "__main__":
    threading.Thread(target=run_web).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    app.run_polling()
