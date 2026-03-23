# commands/pre_game_actions.py

from telegram import Update
from telegram.ext import ContextTypes
from commands.game_admin import get_game
from game.game_controller import Controller
from utils.message_helper import format_player_list
from utils.language import get_message


def _msg(controller, key, **kwargs):
    return get_message(key, lang=controller.language, **kwargs)


async def reply_to_lobby(context, controller: Controller, text: str):
    if controller.lobby_message_id:
        await context.bot.send_message(
            chat_id=controller.group_id,
            text=text,
            reply_to_message_id=controller.lobby_message_id
        )


async def update_lobby_message(context: ContextTypes.DEFAULT_TYPE, controller: Controller):
    if controller.lobby_message_id:
        try:
            creator = await context.bot.get_chat_member(controller.group_id, controller.master_id)
            await context.bot.edit_message_text(
                chat_id=controller.group_id,
                message_id=controller.lobby_message_id,
                text=f"{_msg(controller, 'welcome', user=creator.user.first_name)}\n\n{format_player_list(controller)}"
            )
        except Exception as e:
            print(e)


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    controller = get_game(context, chat.id)

    if not controller:
        await update.message.reply_text(get_message("no_game_join", context))
        return

    success, key = controller.add_player(user.id, user.first_name)
    if success:
        await reply_to_lobby(context, controller, _msg(controller, key, name=user.first_name))
        await update_lobby_message(context, controller)
    else:
        await update.message.reply_text(_msg(controller, key))


async def leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    controller = get_game(context, chat.id)

    if not controller:
        await update.message.reply_text(get_message("no_game", context))
        return

    success, key = controller.remove_player(user.id)
    await update.message.reply_text(_msg(controller, key, name=user.first_name))
    if success:
        await update_lobby_message(context, controller)


async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    controller = get_game(context, chat.id)

    if not controller:
        await update.message.reply_text(get_message("no_game", context))
        return

    if not controller.is_game_master(user.id):
        await update.message.reply_text(_msg(controller, "gm_only"))
        return

    user_id_to_kick = None

    # Method 1: Reply to a message from the player to kick
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        if target and target.id in controller.players:
            user_id_to_kick = target.id

    # Method 2: /kick PlayerName (match by first_name, case-insensitive)
    if not user_id_to_kick and context.args:
        search = " ".join(context.args).lower().lstrip("@")
        for uid, name in controller.players.items():
            if name.lower() == search:
                user_id_to_kick = uid
                break

    if not user_id_to_kick:
        await update.message.reply_text(_msg(controller, "kick_usage"))
        return

    success, key = controller.remove_player(user_id_to_kick)
    kicked_name = controller.players.get(user_id_to_kick, context.args[0] if context.args else "?")
    await update.message.reply_text(_msg(controller, key, name=kicked_name))
    if success:
        await update_lobby_message(context, controller)
