from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CallbackQueryHandler, CommandHandler
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

cursor.execute("""
CREATE TABLE IF NOT EXISTS ips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT
)
""")

conn.commit()

# ================= MENUS =================
def user_menu():
    return ReplyKeyboardMarkup([
        ["📊 My Plan", "🌐 Get IP"],
        ["💰 Buy Plan", "💸 Paid"],
        ["🆔 My ID"]
    ], resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup([
        ["👥 Total Users", "💰 Pending Payments"],
        ["➕ Add IP", "❌ Remove IP"],
        ["📋 IP List"]
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
        await update.message.reply_text("👑 Admin Panel", reply_markup=admin_menu())
    else:
        await update.message.reply_text("👤 User Panel", reply_markup=user_menu())

# ================= USER =================
async def myplan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    cursor.execute("SELECT plan, expire_date FROM users WHERE user_id=?", (uid,))
    data = cursor.fetchone()

    if not data or not data[0] or not data[1]:
        await update.message.reply_text("No active subscription!")
        return

    expire = datetime.strptime(data[1], "%Y-%m-%d %H:%M:%S")

    if datetime.now() > expire:
        await update.message.reply_text("Subscription expired!")
        return

    await update.message.reply_text(f"Plan: {data[0]}\nExpire: {data[1]}")

async def getip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    cursor.execute("SELECT plan, expire_date FROM users WHERE user_id=?", (uid,))
    data = cursor.fetchone()

    if not data or not data[0] or not data[1]:
        await update.message.reply_text("No active subscription!")
        return

    expire = datetime.strptime(data[1], "%Y-%m-%d %H:%M:%S")

    if datetime.now() > expire:
        await update.message.reply_text("Subscription expired!")
        return

    cursor.execute("SELECT ip FROM ips")
    ip = cursor.fetchone()

    if ip:
        await update.message.reply_text(f"Your IP:\n{ip[0]}")
    else:
        await update.message.reply_text("No IP available!")

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
"""💰 Subscription Plans:
Weekly - 100৳
15 Days - 180৳
Monthly - 300৳

📲 Payment: Bkash / Nagad
👉 Pay then press 💸 Paid"""
    )

async def paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    cursor.execute("SELECT * FROM payments WHERE user_id=? AND status='pending'", (uid,))
    if cursor.fetchone():
        await update.message.reply_text("Already submitted!")
        return

    cursor.execute("INSERT INTO payments (user_id, status) VALUES (?, 'pending')", (uid,))
    conn.commit()

    await update.message.reply_text("✅ Payment request sent to admin!")

# ================= ADMIN =================
async def total_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    await update.message.reply_text(f"Total Users: {total}")

async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT user_id FROM payments WHERE status='pending'")
    users = cursor.fetchall()

    if not users:
        await update.message.reply_text("No pending payments!")
        return

    for u in users:
        uid = u[0]

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Approve Weekly", callback_data=f"approve|{uid}|weekly")],
            [InlineKeyboardButton("Approve 15 Days", callback_data=f"approve|{uid}|15days")],
            [InlineKeyboardButton("Approve Monthly", callback_data=f"approve|{uid}|monthly")]
        ])

        await update.message.reply_text(f"User ID: {uid}", reply_markup=keyboard)

# ================= APPROVE =================
async def approve_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split("|")
    uid = int(data[1])
    plan = data[2]

    days = {"weekly":7, "15days":15, "monthly":30}[plan]
    expire = datetime.now() + timedelta(days=days)

    # 🔥 CRITICAL FIX
    cursor.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    if not cursor.fetchone():
        await query.edit_message_text("User not found!")
        return

    cursor.execute(
        "UPDATE users SET plan=?, expire_date=? WHERE user_id=?",
        (plan, expire.strftime("%Y-%m-%d %H:%M:%S"), uid)
    )

    conn.commit()

    # payment update
    cursor.execute("UPDATE payments SET status='approved' WHERE user_id=?", (uid,))
    conn.commit()

    await context.bot.send_message(uid, f"✅ Approved! Plan: {plan}")
    await query.edit_message_text(f"Approved user {uid} ({plan})")

# ================= IP =================
async def add_ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send: /addip ip:port")

async def addip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        ip = context.args[0]
        cursor.execute("INSERT INTO ips (ip) VALUES (?)", (ip,))
        conn.commit()
        await update.message.reply_text(f"IP Added: {ip}")
    except:
        await update.message.reply_text("Usage: /addip ip:port")

async def remove_ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send: /removeip ip")

async def removeip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        ip = context.args[0]
        cursor.execute("DELETE FROM ips WHERE ip=?", (ip,))
        conn.commit()
        await update.message.reply_text(f"Removed: {ip}")
    except:
        await update.message.reply_text("Usage: /removeip ip")

async def list_ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT ip FROM ips")
    ips = cursor.fetchall()

    if not ips:
        await update.message.reply_text("No IP found!")
    else:
        await update.message.reply_text("\n".join([i[0] for i in ips]))

# ================= HANDLER =================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id

    if text == "📊 My Plan":
        await myplan(update, context)

    elif text == "🌐 Get IP":
        await getip(update, context)

    elif text == "💰 Buy Plan":
        await buy(update, context)

    elif text == "💸 Paid":
        await paid(update, context)

    elif text == "🆔 My ID":
        await update.message.reply_text(f"Your ID: {uid}")

    elif text == "👥 Total Users" and uid == ADMIN_ID:
        await total_users(update, context)

    elif text == "💰 Pending Payments" and uid == ADMIN_ID:
        await pending(update, context)

    elif text == "➕ Add IP" and uid == ADMIN_ID:
        await add_ip(update, context)

    elif text == "❌ Remove IP" and uid == ADMIN_ID:
        await remove_ip(update, context)

    elif text == "📋 IP List" and uid == ADMIN_ID:
        await list_ip(update, context)

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
    app.add_handler(CommandHandler("addip", addip_cmd))
    app.add_handler(CommandHandler("removeip", removeip_cmd))

    app.add_handler(CallbackQueryHandler(approve_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    app.run_polling(close_loop=False)
