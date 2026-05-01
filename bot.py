from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from flask import Flask
import threading
import os
import sqlite3

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

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if user.id != ADMIN_ID:
        await update.message.reply_text("You are not admin!")
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    await update.message.reply_text(f"Total Users: {total_users}")

# ================= FLASK =================
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is alive!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port, use_reloader=False)  # 🔥 important

# ================= RUN =================
if __name__ == "__main__":
    threading.Thread(target=run_web).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))

    app.run_polling(close_loop=False)  # 🔥 important
