import os
from dotenv import load_dotenv
from telegram import BotCommand, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from telegram.ext import PicklePersistence
from commands.game_admin import new_game, start_game, handle_variant_callback
from commands.pre_game_actions import join, leave, kick, handle_kick_callback
from commands.language import language, set_language_callback
from commands.game_playflow import (
    handle_team_toggle,
    handle_team_confirm,
    handle_team_vote,
    handle_mission_vote,
    handle_assassin_guess,
    handle_investigate,
    handle_mode_callback,
    handle_mode_done,
    my_role,
    start_command,
    speed,
    handle_speed_callback,
    mode,
    history,
    vote_history,
    abort_game,
)

BOT_COMMANDS = [
    BotCommand("newgame", "Create a new Avalon game"),
    BotCommand("join", "Join the current game"),
    BotCommand("leave", "Leave the current game"),
    BotCommand("startgame", "Start the game (game master)"),
    BotCommand("abort", "Abort the game (game master)"),
    BotCommand("kick", "Kick a player (game master)"),
    BotCommand("speed", "Set game speed / timeout"),
    BotCommand("mode", "Toggle game modes (Lady/Lancelot)"),
    BotCommand("language", "Set language (game master)"),
    BotCommand("myrole", "Check your role (DM)"),
    BotCommand("history", "View mission history"),
    BotCommand("votehistory", "View detailed vote history"),
]


async def post_init(application):
    await application.bot.set_my_commands(BOT_COMMANDS)


def main():
    load_dotenv()
    BOT_TOKEN = os.getenv("BOT_TOKEN")

    os.makedirs("data", exist_ok=True)
    persistence = PicklePersistence(filepath="data/bot_data.pkl")
    app = ApplicationBuilder().token(BOT_TOKEN).persistence(persistence).post_init(post_init).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("myrole", my_role))
    app.add_handler(CommandHandler("newgame", new_game))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("leave", leave))
    app.add_handler(CommandHandler("startgame", start_game))
    app.add_handler(CommandHandler("kick", kick))
    app.add_handler(CommandHandler("abort", abort_game))
    app.add_handler(CommandHandler("language", language))
    app.add_handler(CommandHandler("speed", speed))
    app.add_handler(CommandHandler("mode", mode))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("votehistory", vote_history))

    # Lobby callbacks
    app.add_handler(CallbackQueryHandler(set_language_callback, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(handle_speed_callback, pattern=r"^speed_-?\d+_(fast|medium|slow|none)$"))
    app.add_handler(CallbackQueryHandler(handle_variant_callback, pattern=r"^variant_-?\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_kick_callback, pattern=r"^kick\|"))

    # Mode callbacks (use | separator to avoid underscore conflicts in mode names)
    app.add_handler(CallbackQueryHandler(handle_mode_callback, pattern=r"^mode\|"))
    app.add_handler(CallbackQueryHandler(handle_mode_done, pattern=r"^modedone\|"))
    app.add_handler(CallbackQueryHandler(handle_investigate, pattern=r"^investigate\|"))

    # Game flow callbacks
    app.add_handler(CallbackQueryHandler(handle_team_toggle, pattern=r"^team_-?\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_team_confirm, pattern=r"^teamconfirm_-?\d+$"))
    app.add_handler(CallbackQueryHandler(handle_team_vote, pattern=r"^teamvote_-?\d+_(approve|reject)$"))
    app.add_handler(CallbackQueryHandler(handle_mission_vote, pattern=r"^missionvote_-?\d+_(success|fail)$"))
    app.add_handler(CallbackQueryHandler(handle_assassin_guess, pattern=r"^assassin_-?\d+_\d+$"))

    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
