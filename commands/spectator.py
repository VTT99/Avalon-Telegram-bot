# commands/spectator.py

from telegram import Update
from telegram.ext import ContextTypes
from commands.game_admin import get_game
from utils.language import get_message


def _msg(controller, key, **kwargs):
    return get_message(key, lang=controller.language, **kwargs)


async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/watch — register as a spectator for the active game in this group."""
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text(get_message("use_in_group", context))
        return

    controller = get_game(context, chat.id)
    if not controller:
        await update.message.reply_text(get_message("no_game", context))
        return

    if controller.status == "pre_game_lobby":
        await update.message.reply_text(_msg(controller, "spectator_game_not_started"))
        return

    success, key = controller.add_spectator(user.id, user.first_name)
    if success:
        await update.message.reply_text(
            _msg(controller, key, name=user.first_name,
                 count=len(controller.spectators))
        )
    else:
        await update.message.reply_text(_msg(controller, key))


async def unwatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/unwatch — stop spectating the active game in this group."""
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text(get_message("use_in_group", context))
        return

    controller = get_game(context, chat.id)
    if not controller:
        await update.message.reply_text(get_message("no_game", context))
        return

    success, key = controller.remove_spectator(user.id)
    await update.message.reply_text(_msg(controller, key, name=user.first_name))
