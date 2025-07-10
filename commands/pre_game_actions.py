# commands/player_actions.py

from telegram import Update
from telegram.ext import ContextTypes
from commands.game_admin import get_game

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    game = get_game(context, chat.id)

    if not game:
        await update.message.reply_text("No game. Ask someone to /newgame.")
        return

    success, msg = game.add_player(user.id, user.first_name)
    await update.message.reply_text(msg)
    await update.message.reply_text(f"Current players:\n{game.player_list_text()}")

async def leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    game = get_game(context, chat.id)

    if not game:
        await update.message.reply_text("No game in progress.")
        return

    success, msg = game.remove_player(user.id)
    await update.message.reply_text(msg)
    await update.message.reply_text(f"Current players:\n{game.player_list_text()}")
