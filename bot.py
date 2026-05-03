from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CallbackQueryHandler, CommandHandler
from flask import Flask
import threading
import os
import sqlite3
from datetime import datetime, timedelta

BOT_TOKEN = "8770137480:AAHljo2tSbFlYX9gy7Yl5gd57oSSrUrFrVs"
ADMIN_ID = 2039785960

# ✅ PERSISTENT DB (VERY IMPORTANT)
conn = sqlite3.connect("/data/users.db", check_same_thread=False)
cursor = conn.cursor()

# ================= TABLE =================
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    join_date TEXT,
    plan TEXT,
    expire_date TEXT,
    ip1 TEXT,
    ip2 TEXT,
    ip_count INTEGER DEFAULT 0
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
    ip TEXT,
    used_count INTEGER DEFAULT 0
)
""")

conn.commit()

# ================= MENUS =================
def user_menu():
    return ReplyKeyboardMarkup([
        ["📊 My Plan", "🌐 Get IP"],
        ["🔁 Change IP"],
        ["💰 Buy Plan", "💸 Paid"],
        ["🆔 My ID"]
    ], resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup([
        ["👥 Total Users", "💰 Paid Users"],
        ["💰 Pending Payments"],
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
        await update.message.reply_text("Admin Panel", reply_markup=admin_menu())
    else:
        await update.message.reply_text("User Panel", reply_markup=user_menu())

# ================= SUB CHECK =================
def check_sub(uid):
    cursor.execute("SELECT plan, expire_date FROM users WHERE user_id=?", (uid,))
    data = cursor.fetchone()

    if not data or not data[0]:
        return False

    expire = datetime.strptime(data[1], "%Y-%m-%d %H:%M:%S")
    return datetime.now() < expire

# ================= USER =================
async def myplan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not check_sub(uid):
        await update.message.reply_text("No active subscription!")
        return

    cursor.execute("SELECT plan, expire_date FROM users WHERE user_id=?", (uid,))
    data = cursor.fetchone()

    await update.message.reply_text(f"Plan: {data[0]}\nExpire: {data[1]}")

# ================= IP LOGIC =================
def get_available_ip():
    cursor.execute("SELECT id, ip, used_count FROM ips ORDER BY used_count ASC")
    ips = cursor.fetchall()

    for ip in ips:
        if ip[2] < 3:  # max 3 user per IP
            return ip
    return None

async def getip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not check_sub(uid):
        await update.message.reply_text("No active subscription!")
        return

    cursor.execute("SELECT ip1 FROM users WHERE user_id=?", (uid,))
    data = cursor.fetchone()

    if data and data[0]:
        await update.message.reply_text(f"Your IP:\n{data[0]}")
        return

    ip_data = get_available_ip()

    if not ip_data:
        await update.message.reply_text("IP not available right now contact admin")
        return

    ip_id, ip, count = ip_data

    cursor.execute("UPDATE ips SET used_count=? WHERE id=?", (count+1, ip_id))
    cursor.execute("UPDATE users SET ip1=?, ip_count=1 WHERE user_id=?", (ip, uid))

    conn.commit()

    await update.message.reply_text(f"Your IP:\n{ip}")

# ================= CHANGE IP =================
async def change_ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not check_sub(uid):
        await update.message.reply_text("No active subscription!")
        return

    cursor.execute("SELECT ip_count FROM users WHERE user_id=?", (uid,))
    count = cursor.fetchone()[0]

    if count >= 2:
        await update.message.reply_text("IP change limit reached (2 per week)")
        return

    ip_data = get_available_ip()

    if not ip_data:
        await update.message.reply_text("IP not available right now contact admin")
        return

    ip_id, ip, used = ip_data

    cursor.execute("UPDATE ips SET used_count=? WHERE id=?", (used+1, ip_id))
    cursor.execute("UPDATE users SET ip2=?, ip_count=? WHERE user_id=?", (ip, count+1, uid))

    conn.commit()

    await update.message.reply_text(f"New IP:\n{ip}")

# ================= ADMIN =================
async def total_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT COUNT(*) FROM users")
    await update.message.reply_text(f"Total Users: {cursor.fetchone()[0]}")

async def paid_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT user_id, plan FROM users WHERE plan IS NOT NULL")
    data = cursor.fetchall()

    if not data:
        await update.message.reply_text("No paid users")
        return

    text = "\n".join([f"{u[0]} → {u[1]}" for u in data])
    await update.message.reply_text(text)

# ================= PAYMENTS =================
async def paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cursor.execute("INSERT INTO payments (user_id, status) VALUES (?, 'pending')", (uid,))
    conn.commit()
    await update.message.reply_text("Request sent to admin")

async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT user_id FROM payments WHERE status='pending'")
    users = cursor.fetchall()

    for u in users:
        uid = u[0]
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Approve Weekly", callback_data=f"{uid}|weekly")],
            [InlineKeyboardButton("Approve Monthly", callback_data=f"{uid}|monthly")]
        ])
        await update.message.reply_text(f"{uid}", reply_markup=keyboard)

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid, plan = q.data.split("|")
    uid = int(uid)

    days = 7 if plan=="weekly" else 30
    expire = datetime.now() + timedelta(days=days)

    cursor.execute("UPDATE users SET plan=?, expire_date=? WHERE user_id=?",
                   (plan, expire.strftime("%Y-%m-%d %H:%M:%S"), uid))
    cursor.execute("UPDATE payments SET status='approved' WHERE user_id=?", (uid,))
    conn.commit()

    await context.bot.send_message(uid, f"Approved: {plan}")
    await q.edit_message_text("Approved")

# ================= IP ADMIN =================
async def addip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ip = context.args[0]
    cursor.execute("INSERT INTO ips (ip) VALUES (?)", (ip,))
    conn.commit()
    await update.message.reply_text("IP added")

async def listip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT ip, used_count FROM ips")
    data = cursor.fetchall()
    text = "\n".join([f"{i[0]} ({i[1]}/3)" for i in data])
    await update.message.reply_text(text)

# ================= HANDLER =================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id

    if text == "📊 My Plan":
        await myplan(update, context)

    elif text == "🌐 Get IP":
        await getip(update, context)

    elif text == "🔁 Change IP":
        await change_ip(update, context)

    elif text == "💸 Paid":
        await paid(update, context)

    elif text == "👥 Total Users":
        await total_users(update, context)

    elif text == "💰 Paid Users":
        await paid_users(update, context)

    elif text == "💰 Pending Payments":
        await pending(update, context)

    elif text == "📋 IP List":
        await listip(update, context)

# ================= FLASK =================
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Alive"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port, use_reloader=False)

# ================= RUN =================
if __name__ == "__main__":
    threading.Thread(target=run_web).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addip", addip))

    app.add_handler(CallbackQueryHandler(approve))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    app.run_polling(close_loop=False)
