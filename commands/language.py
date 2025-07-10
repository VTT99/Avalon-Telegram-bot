from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from conf.game_setting import CONFIG
from utils.language import get_message, set_user_language

LANGUAGES = CONFIG["languages"]
DEFAULT_LANG = CONFIG["default_language"]

async def language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton("English", callback_data="lang_en")],
        [InlineKeyboardButton("繁體中文", callback_data="lang_zh-TW")]
    ]
    markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(
        get_message("choose_language", context), reply_markup=markup
    )

async def set_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang_code = query.data.replace("lang_", "")
    if lang_code not in LANGUAGES:
        lang_code = DEFAULT_LANG

    set_user_language(context.user_data, lang_code)
    await query.edit_message_text(get_message("language_selected", context))
