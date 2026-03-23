# commands/game_admin.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from game.game_controller import Controller
from conf import game_setting
from utils.message_helper import format_player_list
from commands.game_playflow import begin_playflow


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

    controller = Controller(chat.id, user.id, game_setting.CONFIG, context.chat_data)
    set_game(context, chat.id, controller)

    message = await update.message.reply_text(
        f"🎲 Game created by {user.first_name}. Players can now /join.\n\n{format_player_list(controller)}"
    )
    controller.lobby_message_id = message.message_id


async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    controller = get_game(context, chat.id)

    if not controller:
        await update.message.reply_text("No game to start.")
        return

    if not controller.is_game_master(user.id):
        await update.message.reply_text("Only the game master can start the game.")
        return

    if not controller.can_start():
        await update.message.reply_text(f"Need at least {controller.min_players} players.")
        return

    # Get available variants
    success, error_msg, variants = controller.get_available_setups()
    if not success:
        await update.message.reply_text(f"❌ {error_msg}")
        return

    if len(variants) == 1:
        # Only one variant — start directly
        await _do_start(context, controller, chat.id, 0)
    else:
        # Multiple variants — let GM choose
        buttons = []
        for i, v in enumerate(variants):
            roles = v["roles"]
            # Deduplicate role names with counts for display
            role_counts = {}
            for r in roles:
                role_counts[r] = role_counts.get(r, 0) + 1
            label = ", ".join(
                f"{count}x{name}" if count > 1 else name
                for name, count in role_counts.items()
            )
            buttons.append([InlineKeyboardButton(
                label, callback_data=f"variant_{chat.id}_{i}"
            )])
        keyboard = InlineKeyboardMarkup(buttons)
        await update.message.reply_text(
            "Choose a role variant:", reply_markup=keyboard
        )


async def handle_variant_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """GM picks a role variant."""
    query = update.callback_query
    parts = query.data.split("_")
    group_id = int(parts[1])
    variant_index = int(parts[2])

    controller = get_game(context, group_id)
    if not controller or controller.status != "pre_game_lobby":
        await query.answer("Game already started.")
        return
    if not controller.is_game_master(query.from_user.id):
        await query.answer("Only the game master can choose.")
        return

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    await query.answer()

    await _do_start(context, controller, group_id, variant_index)


async def _do_start(context, controller, group_id, variant_index):
    """Actually start the game with the given variant."""
    success, error_msg = controller.start_game(variant_index)
    if success:
        await context.bot.send_message(chat_id=group_id, text="🎮 Game started!")
        await begin_playflow(context, controller)
    else:
        await context.bot.send_message(chat_id=group_id, text=f"❌ Failed to start game: {error_msg}")
