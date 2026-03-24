# commands/game_admin.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from game.game_controller import Controller
from conf import game_setting
from utils.message_helper import format_player_list
from utils.language import get_message
from commands.game_playflow import begin_playflow, schedule_lobby_timeout, cancel_timeout


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

    # Schedule lobby expiry
    await schedule_lobby_timeout(context, controller)


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
        # Only one variant — start directly
        await _do_start(context, controller, chat.id, 0)
    else:
        # Multiple variants — let GM choose
        from game.roles import get_role_display_name
        lang = controller.language
        buttons = []
        for i, v in enumerate(variants):
            roles = v["roles"]
            role_counts = {}
            for r in roles:
                role_counts[r] = role_counts.get(r, 0) + 1
            label = ", ".join(
                f"{count}x{get_role_display_name(name, lang)}" if count > 1 else get_role_display_name(name, lang)
                for name, count in role_counts.items()
            )
            buttons.append([InlineKeyboardButton(
                label, callback_data=f"variant_{chat.id}_{i}"
            )])
        keyboard = InlineKeyboardMarkup(buttons)
        await update.message.reply_text(
            _msg(controller, "choose_variant"), reply_markup=keyboard
        )


async def start_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/startcustom — GM picks custom role composition via DM."""
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

    # Initialize custom role selection and DM the GM
    controller.custom_roles = []
    player_count = len(controller.players)

    await update.message.reply_text(_msg(controller, "custom_roles_dm_notice"))

    keyboard = _build_custom_roles_keyboard(controller)
    try:
        await context.bot.send_message(
            chat_id=controller.master_id,
            text=_msg(controller, "custom_roles_header", current=0, total=player_count),
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except Exception:
        await update.message.reply_text(
            _msg(controller, "dm_failed", name="Game Master")
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



def _build_custom_roles_keyboard(controller):
    from game.roles import ROLE_REGISTRY, get_role_display_name, get_alignment
    lang = controller.language
    player_count = len(controller.players)
    custom = controller.custom_roles

    # Count current selections
    role_count = {}
    for r in custom:
        role_count[r] = role_count.get(r, 0) + 1

    # Determine which roles are available
    available_roles = list(ROLE_REGISTRY.keys())
    # If Lancelot mode not enabled, hide Lancelot roles
    if "lancelot" not in controller.enabled_modes:
        available_roles = [r for r in available_roles if not r.startswith("Lancelot") and r != "Guinevere"]

    buttons = []
    for role_name in available_roles:
        display = get_role_display_name(role_name, lang)
        count = role_count.get(role_name, 0)
        alignment = get_alignment(role_name)
        emoji = "😇" if alignment == "good" else "😈"
        label = f"{emoji} {display}"
        if count > 0:
            label += f" x{count}"

        # + and - buttons on same row
        row = [
            InlineKeyboardButton(f"➖", callback_data=f"cr|{controller.group_id}|rem|{role_name}"),
            InlineKeyboardButton(label, callback_data=f"cr|{controller.group_id}|info|{role_name}"),
            InlineKeyboardButton(f"➕", callback_data=f"cr|{controller.group_id}|add|{role_name}"),
        ]
        buttons.append(row)

    # Show/hide roles toggle
    show_icon = "👁️" if controller.show_roles_in_group else "🙈"
    show_label = _msg(controller, "custom_show_roles") if controller.show_roles_in_group else _msg(controller, "custom_hide_roles")
    buttons.append([InlineKeyboardButton(
        f"{show_icon} {show_label}",
        callback_data=f"cr|{controller.group_id}|toggleshow|0"
    )])

    # Confirm button (only if count matches)
    total = len(custom)
    if total == player_count:
        buttons.append([InlineKeyboardButton(
            _msg(controller, "custom_roles_confirm"),
            callback_data=f"cr|{controller.group_id}|confirm|0"
        )])

    return InlineKeyboardMarkup(buttons)


async def handle_custom_role_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """GM adds/removes a role in custom composition."""
    query = update.callback_query
    parts = query.data.split("|")
    group_id = int(parts[1])
    action = parts[2]
    role_name = parts[3]

    controller = get_game(context, group_id)
    if not controller or not controller.is_game_master(query.from_user.id):
        await query.answer()
        return

    if not hasattr(controller, "custom_roles"):
        await query.answer()
        return

    player_count = len(controller.players)
    lang = controller.language

    if action == "add":
        if len(controller.custom_roles) >= player_count:
            await query.answer(_msg(controller, "custom_roles_full"))
            return
        controller.custom_roles.append(role_name)
    elif action == "rem":
        if role_name in controller.custom_roles:
            controller.custom_roles.remove(role_name)
        else:
            await query.answer()
            return
    elif action == "info":
        from game.roles import get_role_display_name
        desc = get_message(f"role_desc_{role_name}", lang=lang)
        await query.answer(desc, show_alert=True)
        return
    elif action == "toggleshow":
        controller.show_roles_in_group = not controller.show_roles_in_group
        # Warn if GM is a player and hiding roles
        if not controller.show_roles_in_group and controller.master_id in controller.players:
            await query.answer(
                get_message("hide_roles_gm_warning", lang=lang), show_alert=True
            )
        else:
            await query.answer()
        # Fall through to rebuild keyboard
    elif action == "confirm":
        if len(controller.custom_roles) != player_count:
            await query.answer(_msg(controller, "custom_roles_count_mismatch"))
            return
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await query.answer()
        await _do_start_custom(context, controller, group_id)
        return

    # Update the keyboard
    keyboard = _build_custom_roles_keyboard(controller)
    try:
        await query.edit_message_text(
            text=_msg(controller, "custom_roles_header",
                      current=len(controller.custom_roles), total=player_count),
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except Exception:
        pass
    await query.answer()


async def _check_mode_warnings(context, controller, group_id):
    """Check for mode/player count warnings. Returns True if we need to wait for confirmation."""
    player_count = len(controller.players)
    warnings = []

    if "lady_of_the_lake" in controller.enabled_modes and player_count < 7:
        warnings.append(_msg(controller, "lady_low_player_warning", count=player_count))

    if "lady_of_the_sea" in controller.enabled_modes and player_count < 7:
        warnings.append(_msg(controller, "lady_sea_low_player_warning", count=player_count))

    if not warnings:
        return False

    text = "\n".join(warnings)
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                _msg(controller, "confirm_start_anyway"),
                callback_data=f"confirmstart|{group_id}"
            ),
            InlineKeyboardButton(
                _msg(controller, "cancel_start"),
                callback_data=f"cancelstart|{group_id}"
            ),
        ]
    ])
    await context.bot.send_message(
        chat_id=group_id, text=text, reply_markup=keyboard, parse_mode="Markdown"
    )
    return True


async def handle_confirm_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """GM confirms starting despite warnings."""
    query = update.callback_query
    parts = query.data.split("|")
    group_id = int(parts[1])

    controller = get_game(context, group_id)
    if not controller or not controller.is_game_master(query.from_user.id):
        await query.answer()
        return

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    await query.answer()

    # Check what was pending
    if hasattr(controller, '_pending_start'):
        kind, arg = controller._pending_start
        del controller._pending_start
        if kind == "preset":
            await _do_start_now(context, controller, group_id, arg)
        elif kind == "custom":
            await _do_start_custom_now(context, controller, group_id)
    else:
        await _do_start_now(context, controller, group_id, 0)


async def handle_cancel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """GM cancels start after warning."""
    query = update.callback_query
    parts = query.data.split("|")
    group_id = int(parts[1])

    controller = get_game(context, group_id)
    if not controller or not controller.is_game_master(query.from_user.id):
        await query.answer()
        return

    if hasattr(controller, '_pending_start'):
        del controller._pending_start

    try:
        await query.edit_message_text(_msg(controller, "start_cancelled"))
    except Exception:
        pass
    await query.answer()


async def _do_start(context, controller, group_id, variant_index):
    """Start with warning check."""
    controller._pending_start = ("preset", variant_index)
    if await _check_mode_warnings(context, controller, group_id):
        return  # waiting for confirmation
    del controller._pending_start
    await _do_start_now(context, controller, group_id, variant_index)


async def _do_start_now(context, controller, group_id, variant_index):
    cancel_timeout(context, group_id)
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


async def _do_start_custom(context, controller, group_id):
    """Start custom with warning check."""
    controller._pending_start = ("custom", None)
    if await _check_mode_warnings(context, controller, group_id):
        return
    del controller._pending_start
    await _do_start_custom_now(context, controller, group_id)


async def _do_start_custom_now(context, controller, group_id):
    cancel_timeout(context, group_id)
    success, error_key = controller.start_game_custom(controller.custom_roles)
    if success:
        await context.bot.send_message(
            chat_id=group_id, text=_msg(controller, "game_started")
        )
        await begin_playflow(context, controller)
    else:
        await context.bot.send_message(
            chat_id=group_id, text=f"❌ {_msg(controller, 'start_failed')}"
        )
