from telegram import Update
from telegram.ext import ContextTypes
from utils.language import get_message


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = get_message("help_text", context)
    await update.message.reply_text(text, parse_mode="HTML")
