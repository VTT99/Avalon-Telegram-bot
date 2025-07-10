# commands/game_admin.py

from telegram import Update
from telegram.ext import ContextTypes
from game.game_controller import AvalonGame

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

    from conf import game_setting
    game = AvalonGame(chat.id, user.id, game_setting.CONFIG)
    set_game(context, chat.id, game)

    await update.message.reply_text(f"🎲 Game created by {user.first_name}. Players can now /join.")

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

async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    game = get_game(context, chat.id)

    if not game:
        await update.message.reply_text("No game in progress.")
        return

    if not game.is_game_master(user.id):
        await update.message.reply_text("Only the game master can kick players.")
        return

    if len(context.args) != 1 or not context.args[0].startswith("@"):
        await update.message.reply_text("Usage: /kick @username")
        return

    username_to_kick = context.args[0][1:]
    user_id_to_kick = None

    for uid, name in game.players.items():
        if name == username_to_kick:
            user_id_to_kick = uid
            break

    if not user_id_to_kick:
        await update.message.reply_text(f"User @{username_to_kick} not found.")
        return

    success, msg = game.remove_player(user_id_to_kick)
    await update.message.reply_text(msg)
    await update.message.reply_text(f"Current players:\n{game.player_list_text()}")
