from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from flask import Flask
import threading

BOT_TOKEN = "8770137480:AAF4R4lCzUZHD2VDMi_47K8iQINZ_TCiXIc"

# Telegram bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is running!")

def run_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()

# Flask server (port open করার জন্য)
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    web_app.run(host="0.0.0.0", port=10000)

# Run both
if __name__ == "__main__":
    t1 = threading.Thread(target=run_bot)
    t1.start()
    run_web()
