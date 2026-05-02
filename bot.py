from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from flask import Flask
import threading
import os
import sqlite3
from datetime import datetime, timedelta
import asyncio

BOT_TOKEN = "8770137480:AAHHnW_qo65bZaCyw8vAY93UdUWWVTKdT_k"
ADMIN_ID = 2039785960

# ================= DATABASE =================
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    join_date TEXT
)
""")

for column, col_type in [
    ("plan", "TEXT"),
    ("expire_date", "TEXT"),
    ("last_ip_time", "TEXT"),
    ("current_ip", "TEXT")
]:
    try:
        cursor.execute(f"ALTER TABLE users ADD COLUMN {column} {col_type}")
    except:
        pass

cursor.execute("""
CREATE TABLE IF NOT EXISTS ips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS ip_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT,
    user_id INTEGER
)
""")

conn.commit()

# ================= MENU =================
def user_menu():
    return ReplyKeyboardMarkup([
        ["📊 My Plan", "🌐 Get IP"],
        ["💰 Buy Plan", "💸 I Paid"],
        ["🆔 My ID"]
    ], resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup([
        ["👥 Total Users", "📋 IP List"],
        ["➕ Add IP", "❌ Remove IP"]
    ], resize_keyboard=True)

# ================= TELEGRAM =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    cursor.execute("SELECT * FROM users WHERE user_id=?", (user.id,))
    data = cursor.fetchone()

    if not data:
        cursor.execute(
            "INSERT INTO users (user_id, username, join_date) VALUES (?, ?, datetime('now'))",
            (user.id, user.username)
        )
        conn.commit()
        text = "Registration successful!"
    else:
        text = "Welcome back!"

    if user.id == ADMIN_ID:
        await update.message.reply_text(text, reply_markup=admin_menu())
    else:
        await update.message.reply_text(text, reply_markup=user_menu())

async def id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your ID: {update.effective_user.id}")

# ================= ADMIN =================
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    await update.message.reply_text(f"Total Users: {total}")

# ================= PAYMENT =================
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
"""💰 Subscription Plans:
Weekly - 100৳
15 Days - 180৳
Monthly - 300৳

📲 Payment: Bkash / Nagad
Send screenshot then press '💸 I Paid'."""
    )

async def paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    msg = f"""
💸 Payment Request

User: @{user.username}
ID: {user.id}

Approve with:
/approve {user.id} weekly
"""

    await context.bot.send_message(ADMIN_ID, msg)
    await update.message.reply_text("✅ Payment request sent. Wait for admin approval.")

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        uid = int(context.args[0])
        plan = context.args[1]

        days = {"weekly":7, "15days":15, "monthly":30}.get(plan)

        if not days:
            await update.message.reply_text("Invalid plan!")
            return

        expire = datetime.now() + timedelta(days=days)

        cursor.execute(
            "UPDATE users SET plan=?, expire_date=? WHERE user_id=?",
            (plan, expire.strftime("%Y-%m-%d %H:%M:%S"), uid)
        )
        conn.commit()

        await context.bot.send_message(uid, f"✅ Payment Approved!\nPlan: {plan}")
        await update.message.reply_text("User approved!")

    except:
        await update.message.reply_text("Usage: /approve user_id plan")

# ================= SUBSCRIPTION =================
async def myplan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    cursor.execute("SELECT plan, expire_date FROM users WHERE user_id=?", (uid,))
    data = cursor.fetchone()

    if data and data[0]:
        await update.message.reply_text(f"Plan: {data[0]}\nExpire: {data[1]}")
    else:
        await update.message.reply_text("No active subscription!")

# ================= IP =================
async def addip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        ip = context.args[0]
        cursor.execute("INSERT INTO ips (ip) VALUES (?)", (ip,))
        conn.commit()
        await update.message.reply_text(f"Added: {ip}")
    except:
        await update.message.reply_text("Usage: /addip ip:port")

async def removeip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        ip = context.args[0]
        cursor.execute("DELETE FROM ips WHERE ip=?", (ip,))
        conn.commit()
        await update.message.reply_text(f"Removed: {ip}")
    except:
        await update.message.reply_text("Usage: /removeip ip")

async def listip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT ip FROM ips")
    data = cursor.fetchall()
    if not data:
        await update.message.reply_text("No IPs!")
    else:
        await update.message.reply_text("\n".join([i[0] for i in data]))

# ================= GET IP =================
async def getip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    cursor.execute("SELECT plan, expire_date, last_ip_time, current_ip FROM users WHERE user_id=?", (user.id,))
    data = cursor.fetchone()

    if not data or not data[0]:
        await update.message.reply_text("No active subscription!")
        return

    expire = datetime.strptime(data[1], "%Y-%m-%d %H:%M:%S")
    if datetime.now() > expire:
        await update.message.reply_text("Subscription expired!")
        return

    if data[2]:
        last = datetime.strptime(data[2], "%Y-%m-%d %H:%M:%S")
        if datetime.now() - last < timedelta(days=2):
            await update.message.reply_text(f"IP:\n{data[3]}\nChange after 2 days.")
            return

    cursor.execute("SELECT ip FROM ips")
    ips = cursor.fetchall()

    selected = None
    for i in ips:
        ip = i[0]
        cursor.execute("SELECT COUNT(*) FROM ip_usage WHERE ip=?", (ip,))
        if cursor.fetchone()[0] < 3:
            selected = ip
            break

    if not selected:
        await update.message.reply_text("No IP available!")
        return

    cursor.execute("INSERT INTO ip_usage (ip, user_id) VALUES (?, ?)", (selected, user.id))
    cursor.execute(
        "UPDATE users SET last_ip_time=?, current_ip=? WHERE user_id=?",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), selected, user.id)
    )
    conn.commit()

    await update.message.reply_text(f"Your IP:\n{selected}")

# ================= BUTTON =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📊 My Plan":
        await myplan(update, context)
    elif text == "🌐 Get IP":
        await getip(update, context)
    elif text == "💰 Buy Plan":
        await buy(update, context)
    elif text == "💸 I Paid":
        await paid(update, context)
    elif text == "🆔 My ID":
        await id(update, context)
    elif text == "👥 Total Users":
        await admin(update, context)
    elif text == "📋 IP List":
        await listip(update, context)
    elif text == "➕ Add IP":
        await update.message.reply_text("Use: /addip ip:port")
    elif text == "❌ Remove IP":
        await update.message.reply_text("Use: /removeip ip")

# ================= EXPIRY =================
async def check_expiry(app):
    while True:
        cursor.execute("SELECT user_id, expire_date FROM users WHERE expire_date IS NOT NULL")
        users = cursor.fetchall()

        for uid, exp in users:
            try:
                expire_time = datetime.strptime(exp, "%Y-%m-%d %H:%M:%S")
                if 0 < (expire_time - datetime.now()).days <= 1:
                    await app.bot.send_message(uid, "⚠️ Expiring soon!")
            except:
                continue

        await asyncio.sleep(3600)

async def on_startup(app):
    asyncio.create_task(check_expiry(app))

# ================= FLASK =================
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is alive!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port, use_reloader=False)

# ================= RUN =================
if __name__ == "__main__":
    threading.Thread(target=run_web).start()

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(on_startup).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", id))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("myplan", myplan))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("paid", paid))
    app.add_handler(CommandHandler("addip", addip))
    app.add_handler(CommandHandler("removeip", removeip))
    app.add_handler(CommandHandler("listip", listip))
    app.add_handler(CommandHandler("getip", getip))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling(close_loop=False)
