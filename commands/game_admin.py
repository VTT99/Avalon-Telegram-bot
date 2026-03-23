# commands/game_admin.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from game.game_controller import Controller
from conf import game_setting
from utils.message_helper import format_player_list
from utils.language import get_message
from commands.game_playflow import begin_playflow


def get_game(context, group_id):
    return context.bot_data.get(f"game_{group_id}")


def set_game(context, group_id, game):
    context.bot_data[f"game_{group_id}"] = game


def _msg(controller, key, **kwargs):
    return get_message(key, lang=controller.language, **kwargs)


async def new_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text(get_message("use_in_group", context))
        return

    if get_game(context, chat.id):
        await update.message.reply_text(get_message("already_exists", context))
        return

    controller = Controller(chat.id, user.id, game_setting.CONFIG, context.chat_data)
    set_game(context, chat.id, controller)

    message = await update.message.reply_text(
        f"{_msg(controller, 'welcome', user=user.first_name)}\n\n{format_player_list(controller)}"
    )
    controller.lobby_message_id = message.message_id


async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    controller = get_game(context, chat.id)

    if not controller:
        await update.message.reply_text(get_message("no_game", context))
        return

    if not controller.is_game_master(user.id):
        await update.message.reply_text(_msg(controller, "gm_only"))
        return

    if not controller.can_start():
        await update.message.reply_text(
            _msg(controller, "need_more_players", count=controller.min_players)
        )
        return

    # Get available variants
    success, error_key, variants = controller.get_available_setups()
    if not success:
        await update.message.reply_text(f"❌ {error_key}")
        return

    if len(variants) == 1:
        await _do_start(context, controller, chat.id, 0)
    else:
        buttons = []
        for i, v in enumerate(variants):
            roles = v["roles"]
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
            _msg(controller, "choose_variant"), reply_markup=keyboard
        )


async def handle_variant_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("_")
    group_id = int(parts[1])
    variant_index = int(parts[2])

    controller = get_game(context, group_id)
    if not controller or controller.status != "pre_game_lobby":
        await query.answer()
        return
    if not controller.is_game_master(query.from_user.id):
        await query.answer(_msg(controller, "gm_only"))
        return

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    await query.answer()

    await _do_start(context, controller, group_id, variant_index)


async def _do_start(context, controller, group_id, variant_index):
    success, error_key = controller.start_game(variant_index)
    if success:
        await context.bot.send_message(
            chat_id=group_id, text=_msg(controller, "game_started")
        )
        await begin_playflow(context, controller)
    else:
        await context.bot.send_message(
            chat_id=group_id, text=f"❌ {_msg(controller, 'start_failed')}"
        )
