from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from flask import Flask
import threading
import os
import sqlite3
from datetime import datetime, timedelta

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
    expire_date TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        ["👥 Total Users"],
        ["💰 Pending Payments"]
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
async def myplan(update: Update):
    uid = update.effective_user.id
    cursor.execute("SELECT plan, expire_date FROM users WHERE user_id=?", (uid,))
    data = cursor.fetchone()

    if data and data[0]:
        await update.message.reply_text(f"Plan: {data[0]}\nExpire: {data[1]}")
    else:
        await update.message.reply_text("No active subscription!")

async def buy(update: Update):
    await update.message.reply_text(
"""💰 Subscription Plans:
Weekly - 100৳
15 Days - 180৳
Monthly - 300৳

📲 Payment: Bkash / Nagad
Then click 💸 Paid"""
    )

async def paid(update: Update):
    uid = update.effective_user.id

    # duplicate avoid
    cursor.execute("SELECT * FROM payments WHERE user_id=? AND status='pending'", (uid,))
    if cursor.fetchone():
        await update.message.reply_text("Already submitted!")
        return

    cursor.execute("INSERT INTO payments (user_id, status) VALUES (?, 'pending')", (uid,))
    conn.commit()

    await update.message.reply_text("✅ Payment submitted!")

# ================= ADMIN =================
async def total_users(update: Update):
    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    await update.message.reply_text(f"Total Users: {total}")

async def pending(update: Update):
    cursor.execute("SELECT user_id FROM payments WHERE status='pending'")
    users = cursor.fetchall()

    if not users:
        await update.message.reply_text("No pending payments!")
        return

    for u in users:
        uid = u[0]

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Weekly", callback_data=f"approve|{uid}|weekly")],
            [InlineKeyboardButton("15 Days", callback_data=f"approve|{uid}|15days")],
            [InlineKeyboardButton("Monthly", callback_data=f"approve|{uid}|monthly")]
        ])

        await update.message.reply_text(f"User ID: {uid}", reply_markup=keyboard)

# ================= APPROVE BUTTON =================
async def approve_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split("|")
    uid = int(data[1])
    plan = data[2]

    days = {"weekly":7, "15days":15, "monthly":30}[plan]
    expire = datetime.now() + timedelta(days=days)

    cursor.execute(
        "UPDATE users SET plan=?, expire_date=? WHERE user_id=?",
        (plan, expire.strftime("%Y-%m-%d %H:%M:%S"), uid)
    )

    cursor.execute("UPDATE payments SET status='approved' WHERE user_id=?", (uid,))
    conn.commit()

    await context.bot.send_message(uid, f"✅ Approved! Plan: {plan}")
    await query.edit_message_text(f"Approved user {uid} ({plan})")

# ================= MESSAGE HANDLER =================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "/start":
        await start(update, context)

    elif text == "📊 My Plan":
        await myplan(update)

    elif text == "🌐 Get IP":
        await update.message.reply_text("IP system working")

    elif text == "💰 Buy Plan":
        await buy(update)

    elif text == "💸 Paid":
        await paid(update)

    elif text == "🆔 My ID":
        await update.message.reply_text(f"Your ID: {user_id}")

    elif text == "👥 Total Users":
        if user_id == ADMIN_ID:
            await total_users(update)

    elif text == "💰 Pending Payments":
        if user_id == ADMIN_ID:
            await pending(update)

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

    app.add_handler(CallbackQueryHandler(approve_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    app.run_polling(close_loop=False)
