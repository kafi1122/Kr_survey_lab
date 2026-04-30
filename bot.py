from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

import os

BOT_TOKEN = ("8770137480:AAF4R4lCzUZHD2VDMi_47K8iQINZ_TCiXIc")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is running!")

app = ApplicationBuilder().token(8770137480:AAF4R4lCzUZHD2VDMi_47K8iQINZ_TCiXIc).build()
app.add_handler(CommandHandler("start", start))

app.run_polling()
