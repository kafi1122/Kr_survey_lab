from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
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
    join_date TEXT
)
""")
conn.commit()

# 🔥 Add new columns safely
try:
    cursor.execute("ALTER TABLE users ADD COLUMN plan TEXT")
except:
    pass

try:
    cursor.execute("ALTER TABLE users ADD COLUMN expire_date TEXT")
except:
    pass

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

# ================= ADMIN =================
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if user.id != ADMIN_ID:
        await update.message.reply_text("You are not admin!")
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    await update.message.reply_text(f"Total Users: {total_users}")

# ================= SET PLAN =================
async def setplan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if user.id != ADMIN_ID:
        await update.message.reply_text("You are not admin!")
        return

    try:
        target_id = int(context.args[0])
        plan = context.args[1]

        if plan == "weekly":
            days = 7
        elif plan == "15days":
            days = 15
        elif plan == "monthly":
            days = 30
        else:
            await update.message.reply_text("Invalid plan!")
            return

        expire = datetime.now() + timedelta(days=days)

        cursor.execute(
            "UPDATE users SET plan=?, expire_date=? WHERE user_id=?",
            (plan, expire.strftime("%Y-%m-%d %H:%M:%S"), target_id)
        )
        conn.commit()

        await update.message.reply_text(f"Plan set for {target_id}: {plan}")

    except:
        await update.message.reply_text("Usage: /setplan user_id plan")

# ================= USER PLAN =================
async def myplan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    cursor.execute("SELECT plan, expire_date FROM users WHERE user_id=?", (user.id,))
    data = cursor.fetchone()

    if data and data[0]:
        await update.message.reply_text(f"Plan: {data[0]}\nExpire: {data[1]}")
    else:
        await update.message.reply_text("No active subscription!")

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
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("setplan", setplan))
    app.add_handler(CommandHandler("myplan", myplan))

    app.run_polling(close_loop=False)
