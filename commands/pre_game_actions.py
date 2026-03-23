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

    if controller.status != "pre_game_lobby":
        await update.message.reply_text(_msg(controller, "game_already_started"))
        return

    # Show inline buttons with player list (exclude GM)
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    buttons = []
    for uid, name in controller.players.items():
        if uid != controller.master_id:
            buttons.append([InlineKeyboardButton(
                name, callback_data=f"kick|{chat.id}|{uid}"
            )])

    if not buttons:
        await update.message.reply_text(_msg(controller, "no_players_to_kick"))
        return

    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(
        _msg(controller, "kick_prompt"), reply_markup=keyboard
    )


async def handle_kick_callback(update, context):
    """GM picks a player to kick via inline button."""
    query = update.callback_query
    parts = query.data.split("|")
    group_id = int(parts[1])
    target_uid = int(parts[2])

    controller = get_game(context, group_id)
    if not controller or controller.status != "pre_game_lobby":
        await query.answer(get_message("game_already_started"))
        return
    if not controller.is_game_master(query.from_user.id):
        await query.answer(get_message("gm_only"))
        return

    name = controller.players.get(target_uid, "?")
    success, key = controller.remove_player(target_uid)

    try:
        await query.edit_message_text(_msg(controller, key, name=name))
    except Exception:
        pass
    await query.answer()

    if success:
        await update_lobby_message(context, controller)
