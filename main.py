import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from telegram.ext import PicklePersistence
from commands.game_admin import new_game, start_game, kick
from commands.pre_game_actions import join, leave
from commands.language import language, set_language_callback

def main():
    load_dotenv()
    BOT_TOKEN = os.getenv("BOT_TOKEN")

    os.makedirs("data", exist_ok=True)
    persistence = PicklePersistence(filepath="data/bot_data.pkl")
    app = ApplicationBuilder().token(BOT_TOKEN).persistence(persistence).build()

    app.add_handler(CommandHandler("newgame", new_game))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("leave", leave))
    app.add_handler(CommandHandler("startgame", start_game))
    app.add_handler(CommandHandler("kick", kick))
    app.add_handler(CommandHandler("language", language))
    app.add_handler(CallbackQueryHandler(set_language_callback, pattern="^lang_"))
    
    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
