# commands/game_admin.py

from telegram import Update
from telegram.ext import ContextTypes
from game.game_controller import AvalonGame
from conf import game_setting
from utils.message_helper import format_player_list

def get_game(context, group_id):
    return context.bot_data.get(f"game_{group_id}")

def set_game(context, group_id, game):
    context.bot_data[f"game_{group_id}"] = game

async def new_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("Use this command in a group.")
        return

    if get_game(context, chat.id):
        await update.message.reply_text("A game already exists.")
        return

    game = AvalonGame(chat.id, user.id, game_setting.CONFIG)
    set_game(context, chat.id, game)

    # Send lobby message and store message ID
    message = await update.message.reply_text(
        f"🎲 Game created by {user.first_name}. Players can now /join.\n\n{format_player_list(game)}"
    )
    game.lobby_message_id = message.message_id


async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    game = get_game(context, chat.id)

    if not game:
        await update.message.reply_text("No game to start.")
        return

    if not game.is_game_master(user.id):
        await update.message.reply_text("Only the game master can start the game.")
        return

    if not game.can_start():
        await update.message.reply_text(f"Need at least {game.min_players} players.")
        return

    game.start_game()
    await update.message.reply_text("🎮 Game started! (TODO: assign roles...)")
