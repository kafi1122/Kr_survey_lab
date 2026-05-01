from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
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

# users table
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    join_date TEXT
)
""")

# add columns safely
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

# IP tables
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

# ================= TELEGRAM =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    cursor.execute("SELECT * FROM users WHERE user_id=?", (user.id,))
    data = cursor.fetchone()

    if data:
        await update.message.reply_text("Welcome back!")
    else:
        cursor.execute(
            "INSERT INTO users (user_id, username, join_date) VALUES (?, ?, datetime('now'))",
            (user.id, user.username)
        )
        conn.commit()
        await update.message.reply_text("Registration successful!")

async def id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your ID: {update.effective_user.id}")

# ================= ADMIN =================
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("You are not admin!")
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    await update.message.reply_text(f"Total Users: {total}")

# ================= SUBSCRIPTION =================
async def setplan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("You are not admin!")
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

        await update.message.reply_text(f"Plan set: {plan}")
    except:
        await update.message.reply_text("Usage: /setplan user_id plan")

async def myplan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    cursor.execute("SELECT plan, expire_date FROM users WHERE user_id=?", (uid,))
    data = cursor.fetchone()

    if data and data[0]:
        await update.message.reply_text(f"Plan: {data[0]}\nExpire: {data[1]}")
    else:
        await update.message.reply_text("No active subscription!")

# ================= PAYMENT =================
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """💰 Subscription Plans:

Weekly (7 days) - 100৳
15 Days - 180৳
Monthly (30 days) - 300৳

📲 Payment Method:
Bkash / Nagad

Send screenshot after payment to admin."""
    await update.message.reply_text(text)

# ================= IP MANAGEMENT =================
async def addip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("You are not admin!")
        return

    try:
        ip = context.args[0]
        cursor.execute("INSERT INTO ips (ip) VALUES (?)", (ip,))
        conn.commit()
        await update.message.reply_text(f"IP Added: {ip}")
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
    ips = cursor.fetchall()

    if not ips:
        await update.message.reply_text("No IPs found!")
        return

    text = "\n".join([i[0] for i in ips])
    await update.message.reply_text(f"IP List:\n{text}")

# ================= ADVANCED GET IP =================
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

    last_time = data[2]
    current_ip = data[3]

    if last_time:
        last_time = datetime.strptime(last_time, "%Y-%m-%d %H:%M:%S")
        if datetime.now() - last_time < timedelta(days=2):
            await update.message.reply_text(
                f"You already have IP:\n{current_ip}\n\nChange after 2 days."
            )
            return

    cursor.execute("SELECT ip FROM ips")
    ips = cursor.fetchall()

    selected_ip = None

    for ip_row in ips:
        ip = ip_row[0]
        cursor.execute("SELECT COUNT(*) FROM ip_usage WHERE ip=?", (ip,))
        count = cursor.fetchone()[0]

        if count < 3:
            selected_ip = ip
            break

    if not selected_ip:
        await update.message.reply_text("No IP available!")
        return

    cursor.execute("INSERT INTO ip_usage (ip, user_id) VALUES (?, ?)", (selected_ip, user.id))

    cursor.execute(
        "UPDATE users SET last_ip_time=?, current_ip=? WHERE user_id=?",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), selected_ip, user.id)
    )

    conn.commit()

    await update.message.reply_text(f"Your New IP:\n{selected_ip}")

# ================= EXPIRY CHECK =================
async def check_expiry(app):
    while True:
        cursor.execute("SELECT user_id, expire_date FROM users WHERE expire_date IS NOT NULL")
        users = cursor.fetchall()

        for uid, exp in users:
            expire_time = datetime.strptime(exp, "%Y-%m-%d %H:%M:%S")

            if 0 < (expire_time - datetime.now()).days <= 1:
                try:
                    await app.bot.send_message(uid, "⚠️ Your subscription will expire soon!")
                except:
                    pass

        await asyncio.sleep(3600)

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

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", id))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("setplan", setplan))
    app.add_handler(CommandHandler("myplan", myplan))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("addip", addip))
    app.add_handler(CommandHandler("removeip", removeip))
    app.add_handler(CommandHandler("listip", listip))
    app.add_handler(CommandHandler("getip", getip))

    loop = asyncio.get_event_loop()
    loop.create_task(check_expiry(app))

    app.run_polling(close_loop=False)
