from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
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
    join_date TEXT,
    plan TEXT,
    expire_date TEXT,
    last_ip_time TEXT,
    current_ip TEXT
)
""")

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

# NEW TABLE (pending payment)
cursor.execute("""
CREATE TABLE IF NOT EXISTS payments (
    user_id INTEGER,
    status TEXT
)
""")

conn.commit()

# ================= MENU =================
def user_menu():
    return ReplyKeyboardMarkup([
        ["📊 My Plan", "🌐 Get IP"],
        ["💰 Buy Plan", "💸 Paid"],
        ["🆔 My ID"]
    ], resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup([
        ["👥 Total Users", "📋 IP List"],
        ["💰 Pending Payments"],
        ["➕ Add IP", "❌ Remove IP"]
    ], resize_keyboard=True)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    cursor.execute("SELECT * FROM users WHERE user_id=?", (user.id,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (user_id, username, join_date) VALUES (?, ?, datetime('now'))",
            (user.id, user.username)
        )
        conn.commit()

    if user.id == ADMIN_ID:
        await update.message.reply_text("Admin Panel", reply_markup=admin_menu())
    else:
        await update.message.reply_text("Welcome!", reply_markup=user_menu())

# ================= USER =================
async def myplan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cursor.execute("SELECT plan, expire_date FROM users WHERE user_id=?", (uid,))
    data = cursor.fetchone()

    if data and data[0]:
        await update.message.reply_text(f"Plan: {data[0]}\nExpire: {data[1]}")
    else:
        await update.message.reply_text("No active subscription!")

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
"""💰 Subscription Plans:
Weekly - 100৳
15 Days - 180৳
Monthly - 300৳

📲 Payment: Bkash / Nagad
Then click '💸 Paid'"""
    )

# ================= PAYMENT =================
async def paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    cursor.execute("INSERT INTO payments (user_id, status) VALUES (?, 'pending')", (uid,))
    conn.commit()

    await update.message.reply_text("✅ Payment request sent!")

# ================= ADMIN =================
async def total_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    await update.message.reply_text(f"Total Users: {total}")

async def pending_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT user_id FROM payments WHERE status='pending'")
    users = cursor.fetchall()

    if not users:
        await update.message.reply_text("No pending payments!")
        return

    for u in users:
        uid = u[0]

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Approve Weekly", callback_data=f"approve_{uid}_weekly")],
            [InlineKeyboardButton("Approve Monthly", callback_data=f"approve_{uid}_monthly")]
        ])

        await update.message.reply_text(f"User ID: {uid}", reply_markup=keyboard)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split("_")
    uid = int(data[1])
    plan = data[2]

    days = {"weekly":7, "monthly":30}.get(plan)

    expire = datetime.now() + timedelta(days=days)

    cursor.execute(
        "UPDATE users SET plan=?, expire_date=? WHERE user_id=?",
        (plan, expire.strftime("%Y-%m-%d %H:%M:%S"), uid)
    )

    cursor.execute("UPDATE payments SET status='approved' WHERE user_id=?", (uid,))
    conn.commit()

    await context.bot.send_message(uid, f"✅ Approved! Plan: {plan}")
    await query.edit_message_text(f"Approved user {uid}")

# ================= IP =================
async def addip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    ip = context.args[0]
    cursor.execute("INSERT INTO ips (ip) VALUES (?)", (ip,))
    conn.commit()
    await update.message.reply_text("IP Added!")

async def listip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT ip FROM ips")
    ips = cursor.fetchall()
    if not ips:
        await update.message.reply_text("No IPs!")
    else:
        await update.message.reply_text("\n".join([i[0] for i in ips]))

# ================= GET IP =================
async def getip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    cursor.execute("SELECT plan, expire_date FROM users WHERE user_id=?", (uid,))
    data = cursor.fetchone()

    if not data or not data[0]:
        await update.message.reply_text("No active subscription!")
        return

    await update.message.reply_text("IP system working")

# ================= MESSAGE =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📊 My Plan":
        await myplan(update, context)
    elif text == "🌐 Get IP":
        await getip(update, context)
    elif text == "💰 Buy Plan":
        await buy(update, context)
    elif text == "💸 Paid":
        await paid(update, context)
    elif text == "👥 Total Users":
        await total_users(update, context)
    elif text == "📋 IP List":
        await listip(update, context)
    elif text == "💰 Pending Payments":
        await pending_payments(update, context)

# ================= FLASK =================
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot alive"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port, use_reloader=False)

# ================= RUN =================
if __name__ == "__main__":
    threading.Thread(target=run_web).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling(close_loop=False)
