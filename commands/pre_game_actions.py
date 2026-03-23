# commands/player_actions.py

from telegram import Update
from telegram.ext import ContextTypes
from commands.game_admin import get_game
from game.game_controller import Controller
from utils.message_helper import format_player_list

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
                text=f"🎲 Game created by {creator.user.first_name}. Players can now /join.\n\n{format_player_list(controller)}"
            )
        except Exception as e:
            print(e)
            # logger.warning(f"Failed to edit lobby message: {e}")

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    controller = get_game(context, chat.id)

    if not controller:
        await update.message.reply_text("No game. Ask someone to /newgame.")
        return

    success, msg = controller.add_player(user.id, user.first_name)
    if success:
        await reply_to_lobby(context, controller, "You joined the game!")
        await update_lobby_message(context, controller)
    else:
        await update.message.reply_text(msg)

async def leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    controller = get_game(context, chat.id)

    if not controller:
        await update.message.reply_text("No game in progress.")
        return

    success, msg = controller.remove_player(user.id)
    await update.message.reply_text(msg)
    if success:
        await update_lobby_message(context, controller)


async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    controller = get_game(context, chat.id)

    if not controller:
        await update.message.reply_text("No game in progress.")
        return

    if not controller.is_game_master(user.id):
        await update.message.reply_text("Only the game master can kick players.")
        return

    if len(context.args) != 1 or not context.args[0].startswith("@"):
        await update.message.reply_text("Usage: /kick @username")
        return

    username_to_kick = context.args[0][1:]
    user_id_to_kick = None

    for uid, name in controller.players.items():
        if name == username_to_kick:
            user_id_to_kick = uid
            break

    if not user_id_to_kick:
        await update.message.reply_text(f"User @{username_to_kick} not found.")
        return

    success, msg = controller.remove_player(user_id_to_kick)
    await update.message.reply_text(msg)
    if success:
        await update_lobby_message(context, controller)
