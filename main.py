import os
import sys

# Must set debug env var before any game imports
if "--debug" in sys.argv:
    os.environ["AVALON_DEBUG"] = "1"

from dotenv import load_dotenv
from telegram import BotCommand, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from telegram.ext import PicklePersistence
from commands.game_admin import (
    new_game, start_game, start_custom, handle_variant_callback,
    handle_custom_role_action, handle_confirm_start, handle_cancel_start,
)
from commands.pre_game_actions import join, leave, kick, handle_kick_callback, handle_join_callback
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
    handle_extend,
    handle_config_stage,
    handle_config_set,
    handle_config_extend,
    handle_config_done,
    config,
    handle_excalibur,
    handle_skip_discussion,
    roles_command,
    handle_role_info_callback,
    stats_command,
    my_role,
    start_command,
    speed,
    handle_speed_callback,
    mode,
    history,
    vote_history,
    abort_game,
    reveal_command,
    handle_reveal_callback,
)

BOT_COMMANDS = [
    BotCommand("newgame", "Create a new Avalon game"),
    BotCommand("join", "Join the current game"),
    BotCommand("leave", "Leave the current game"),
    BotCommand("startgame", "Start with preset roles"),
    BotCommand("startcustom", "Start with custom roles"),
    BotCommand("abort", "Abort the game (game master)"),
    BotCommand("kick", "Kick a player (game master)"),
    BotCommand("speed", "Quick speed preset"),
    BotCommand("timeoutconfig", "Configure per-stage timeouts"),
    BotCommand("mode", "Toggle game modes (Lady/Lancelot)"),
    BotCommand("language", "Set language (game master)"),
    BotCommand("myrole", "Check your role (DM)"),
    BotCommand("roles", "List all roles and descriptions"),
    BotCommand("history", "View mission history"),
    BotCommand("votehistory", "View detailed vote history"),
    BotCommand("stats", "View win/loss leaderboard"),
    BotCommand("reveal", "Reveal your Good loyalty card to a player (Revealer role)"),
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
    app.add_handler(CommandHandler("startcustom", start_custom))
    app.add_handler(CommandHandler("kick", kick))
    app.add_handler(CommandHandler("abort", abort_game))
    app.add_handler(CommandHandler("language", language))
    app.add_handler(CommandHandler("speed", speed))
    app.add_handler(CommandHandler("timeoutconfig", config))
    app.add_handler(CommandHandler("mode", mode))
    app.add_handler(CommandHandler("roles", roles_command))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("votehistory", vote_history))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("reveal", reveal_command))

    # Lobby callbacks
    app.add_handler(CallbackQueryHandler(set_language_callback, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(handle_speed_callback, pattern=r"^speed_-?\d+_(fast|medium|slow|none)$"))
    app.add_handler(CallbackQueryHandler(handle_variant_callback, pattern=r"^variant_-?\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_custom_role_action, pattern=r"^cr\|"))
    app.add_handler(CallbackQueryHandler(handle_kick_callback, pattern=r"^kick\|"))
    app.add_handler(CallbackQueryHandler(handle_confirm_start, pattern=r"^confirmstart\|"))
    app.add_handler(CallbackQueryHandler(handle_cancel_start, pattern=r"^cancelstart\|"))
    app.add_handler(CallbackQueryHandler(handle_join_callback, pattern=r"^join\|"))

    # Config callbacks
    app.add_handler(CallbackQueryHandler(handle_config_stage, pattern=r"^cfg\|"))
    app.add_handler(CallbackQueryHandler(handle_config_set, pattern=r"^cfgset\|"))
    app.add_handler(CallbackQueryHandler(handle_config_extend, pattern=r"^cfgext\|"))
    app.add_handler(CallbackQueryHandler(handle_config_done, pattern=r"^cfgdone\|"))
    app.add_handler(CallbackQueryHandler(handle_extend, pattern=r"^extend\|"))

    # Mode callbacks
    app.add_handler(CallbackQueryHandler(handle_mode_callback, pattern=r"^mode\|"))
    app.add_handler(CallbackQueryHandler(handle_mode_done, pattern=r"^modedone\|"))
    app.add_handler(CallbackQueryHandler(handle_investigate, pattern=r"^investigate\|"))
    app.add_handler(CallbackQueryHandler(handle_excalibur, pattern=r"^excalibur\|"))
    app.add_handler(CallbackQueryHandler(handle_skip_discussion, pattern=r"^skipdiscuss\|"))

    # Game flow callbacks
    app.add_handler(CallbackQueryHandler(handle_team_toggle, pattern=r"^team_-?\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_team_confirm, pattern=r"^teamconfirm_-?\d+$"))
    app.add_handler(CallbackQueryHandler(handle_team_vote, pattern=r"^teamvote_-?\d+_(approve|reject)$"))
    app.add_handler(CallbackQueryHandler(handle_mission_vote, pattern=r"^missionvote_-?\d+_(success|fail)$"))
    app.add_handler(CallbackQueryHandler(handle_assassin_guess, pattern=r"^assassin_-?\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_role_info_callback, pattern=r"^roleinfo\|"))
    app.add_handler(CallbackQueryHandler(handle_reveal_callback, pattern=r"^reveal\|"))

    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    if os.environ.get("AVALON_DEBUG") == "1":
        print("⚠️  Debug mode enabled (2-4 player configs available)")
    main()
