from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from conf.game_setting import CONFIG
from utils.language import get_message, set_user_language
from commands.game_admin import get_game

LANGUAGES = CONFIG["languages"]
DEFAULT_LANG = CONFIG["default_language"]


async def language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    # In group: only GM (or anyone if no game) can change language
    if chat.type in ("group", "supergroup"):
        controller = get_game(context, chat.id)
        if controller and not controller.is_game_master(update.effective_user.id):
            await update.message.reply_text(
                get_message("language_gm_only", lang=controller.language)
            )
            return

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

    chat = query.message.chat
    if chat.type in ("group", "supergroup"):
        # Group: check GM permission, set group-persistent language
        controller = get_game(context, chat.id)
        if controller and not controller.is_game_master(query.from_user.id):
            return

        # Persist in chat_data (survives across games)
        context.chat_data["lang"] = lang_code

        # Also update current controller if exists
        if controller:
            controller.language = lang_code

        await query.edit_message_text(
            get_message("game_language_set", lang=lang_code)
        )
    else:
        # DM: set personal language
        set_user_language(context.user_data, lang_code)
        await query.edit_message_text(get_message("language_selected", lang=lang_code))
