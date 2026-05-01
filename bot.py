from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from flask import Flask
import threading
import os

BOT_TOKEN = "8770137480:AAFE6WOePbgvdKcqy8_pq3k9KhgrGTgfer4"

# Telegram bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is running!")

# Flask app (port keep alive)
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is alive!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # Flask background এ চালাও
    threading.Thread(target=run_web).start()

    # Bot main thread এ চালাও (IMPORTANT)
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()
