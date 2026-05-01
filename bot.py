from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from flask import Flask
import threading
import asyncio

BOT_TOKEN = "8770137480:AAFE6WOePbgvdKcqy8_pq3k9KhgrGTgfer4"

# Telegram handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is running!")

# Run bot
def run_bot():
    async def main():
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        await app.run_polling()
    asyncio.run(main())

# Flask app
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    web_app.run(host="0.0.0.0", port=10000)

# Run both
if __name__ == "__main__":
    t = threading.Thread(target=run_bot)
    t.start()
    run_web()
