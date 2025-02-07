from telegram import Update
from telegram.ext import ContextTypes, CommandHandler


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to the Boltz Pro fee alert bot! Use /subscribe to receive fee updates."
    )


start_handler = CommandHandler("start", start)
