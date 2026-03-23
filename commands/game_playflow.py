# commands/game_playflow.py

import random as _random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from game.roles import is_evil as is_evil_role, get_vision, evil_role_names, get_role_display_name
from utils.language import get_message, get_button_text

SPEED_PRESETS = {
    "fast": {"lobby": 2, "team_select": 2, "team_vote": 2, "mission_vote": 2, "assassin_guess": 2, "investigate": 2, "discussion": 0},
    "medium": {"lobby": 5, "team_select": 5, "team_vote": 5, "mission_vote": 5, "assassin_guess": 5, "investigate": 5, "discussion": 2},
    "slow": {"lobby": 10, "team_select": 30, "team_vote": 30, "mission_vote": 30, "assassin_guess": 30, "investigate": 30, "discussion": 5},
    "none": {"lobby": 0, "team_select": 0, "team_vote": 0, "mission_vote": 0, "assassin_guess": 0, "investigate": 0, "discussion": 0},
}

STAGE_KEYS = ["lobby", "team_select", "team_vote", "mission_vote", "assassin_guess", "investigate", "discussion"]


def get_game_from_callback(context, callback_data, prefix):
    """Extract group_id from callback data and return the controller."""
    parts = callback_data.split("_")
    prefix_parts = prefix.count("_") + 1
    group_id = int(parts[prefix_parts])
    return context.bot_data.get(f"game_{group_id}"), group_id


def msg(key, controller, **kwargs):
    """Shortcut: get_message with game language."""
    return get_message(key, lang=controller.language, **kwargs)


def btn(key, controller):
    """Shortcut: get_button_text with game language."""
    return get_button_text(key, lang=controller.language)


# --- Timeout helpers ---

def _timeout_job_name(group_id):
    return f"timeout_{group_id}"


def _reminder_job_name(group_id, suffix=""):
    return f"reminder_{group_id}{suffix}"


async def _timeout_reminder(context):
    """Send a 30s warning before auto-action (in-game phases)."""
    group_id = context.job.data
    controller = context.bot_data.get(f"game_{group_id}")
    if not controller or controller.status in ("pre_game_lobby", "game_over"):
        return

    # Include extend button if allowed
    text = msg("timeout_reminder", controller)
    reply_markup = None
    if controller.allow_extend and not controller.extend_used:
        reply_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                get_message("extend_button", lang=controller.language),
                callback_data=f"extend|{group_id}"
            )
        ]])

    await context.bot.send_message(
        chat_id=group_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def _lobby_reminder(context):
    """Send a lobby closing warning."""
    group_id, secs_left = context.job.data
    controller = context.bot_data.get(f"game_{group_id}")
    if not controller or controller.status != "pre_game_lobby":
        return
    await context.bot.send_message(
        chat_id=group_id,
        text=get_message("lobby_closing", lang=controller.language, seconds=secs_left),
        parse_mode="Markdown"
    )


def schedule_timeout_for_stage(context, controller, stage: str, callback):
    """Schedule a timeout for a specific game stage. No-op if timeout is 0."""
    cancel_timeout(context, controller.group_id)
    controller.extend_used = False  # reset extend for new phase

    minutes = controller.timeouts.get(stage, 0)
    if minutes <= 0:
        return

    seconds = minutes * 60
    group_id = controller.group_id

    if stage == "lobby":
        # Lobby gets 60s and 30s reminders
        if seconds > 60:
            context.job_queue.run_once(
                _lobby_reminder,
                when=seconds - 60,
                data=(group_id, 60),
                name=_reminder_job_name(group_id, "_60"),
            )
        if seconds > 30:
            context.job_queue.run_once(
                _lobby_reminder,
                when=seconds - 30,
                data=(group_id, 30),
                name=_reminder_job_name(group_id, "_30"),
            )
    else:
        # In-game phases get a 30s reminder
        if seconds > 30:
            context.job_queue.run_once(
                _timeout_reminder,
                when=seconds - 30,
                data=group_id,
                name=_reminder_job_name(group_id),
            )

    context.job_queue.run_once(
        callback,
        when=seconds,
        data=group_id,
        name=_timeout_job_name(group_id),
    )


async def handle_extend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Player extends the current timeout by 2 minutes."""
    query = update.callback_query
    parts = query.data.split("|")
    group_id = int(parts[1])

    from commands.game_admin import get_game
    controller = get_game(context, group_id)
    if not controller or not controller.allow_extend:
        await query.answer()
        return

    if controller.extend_used:
        await query.answer(get_message("extend_already_used", lang=controller.language))
        return

    controller.extend_used = True

    # Cancel current timeout and reminder, reschedule with +2 min
    jobs = context.job_queue.get_jobs_by_name(_timeout_job_name(group_id))
    if jobs:
        job = jobs[0]
        remaining = (job.next_t - job.next_t.now(job.next_t.tzinfo)).total_seconds()
        new_seconds = max(remaining, 0) + 120  # add 2 minutes

        # Get the callback from the existing job
        callback = job.callback
        cancel_timeout(context, group_id)

        context.job_queue.run_once(
            callback,
            when=new_seconds,
            data=group_id,
            name=_timeout_job_name(group_id),
        )

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    player_name = controller.players.get(query.from_user.id, query.from_user.first_name)
    await context.bot.send_message(
        chat_id=group_id,
        text=get_message("timeout_extended", lang=controller.language, name=player_name),
        parse_mode="Markdown"
    )
    await query.answer()


def cancel_timeout(context, group_id):
    """Cancel any pending timeout and reminders for this game."""
    names = [
        _timeout_job_name(group_id),
        _reminder_job_name(group_id),
        _reminder_job_name(group_id, "_60"),
        _reminder_job_name(group_id, "_30"),
    ]
    for name in names:
        for job in context.job_queue.get_jobs_by_name(name):
            job.schedule_removal()


# --- Speed command ---

async def speed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/speed — pick game speed (timeout per phase)."""
    from commands.game_admin import get_game
    chat = update.effective_chat
    controller = get_game(context, chat.id)

    if not controller or controller.status != "pre_game_lobby":
        await update.message.reply_text(get_message("use_in_lobby", context))
        return

    if not controller.is_game_master(update.effective_user.id):
        await update.message.reply_text(get_message("gm_only", context))
        return

    lang = controller.language
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(get_message("speed_fast", lang=lang), callback_data=f"speed_{chat.id}_fast"),
            InlineKeyboardButton(get_message("speed_medium", lang=lang), callback_data=f"speed_{chat.id}_medium"),
        ],
        [
            InlineKeyboardButton(get_message("speed_slow", lang=lang), callback_data=f"speed_{chat.id}_slow"),
            InlineKeyboardButton(get_message("speed_none", lang=lang), callback_data=f"speed_{chat.id}_none"),
        ]
    ])
    await update.message.reply_text(
        msg("choose_speed", controller), reply_markup=keyboard
    )


async def handle_speed_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle speed selection."""
    query = update.callback_query
    parts = query.data.split("_")
    group_id = int(parts[1])
    preset = parts[2]

    from commands.game_admin import get_game
    controller = get_game(context, group_id)
    if not controller or controller.status != "pre_game_lobby":
        await query.answer(get_message("game_already_started"))
        return
    if not controller.is_game_master(query.from_user.id):
        await query.answer(get_message("gm_only"))
        return

    controller.timeouts.update(SPEED_PRESETS[preset])
    label = get_message(f"speed_{preset}", lang=controller.language)
    try:
        await query.edit_message_text(msg("speed_set", controller, speed=label))
    except Exception:
        pass
    await query.answer()


# --- Mode command ---

async def mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/mode — toggle game modes in lobby."""
    from commands.game_admin import get_game
    chat = update.effective_chat
    controller = get_game(context, chat.id)

    if not controller or controller.status != "pre_game_lobby":
        await update.message.reply_text(get_message("use_in_lobby", context))
        return
    if not controller.is_game_master(update.effective_user.id):
        await update.message.reply_text(get_message("gm_only", context))
        return

    keyboard = _build_mode_keyboard(controller)
    await update.message.reply_text(
        msg("choose_mode", controller), reply_markup=keyboard
    )


def _build_mode_keyboard(controller):
    from game.game_modes import get_available_modes, MODE_METADATA
    lang = controller.language
    buttons = []
    for mode_name in get_available_modes():
        meta = MODE_METADATA.get(mode_name, {})
        emoji = meta.get("emoji", "")
        display = get_message(f"mode_name_{mode_name}", lang=lang)
        enabled = mode_name in controller.enabled_modes
        prefix = "✅ " if enabled else "❌ "
        buttons.append([InlineKeyboardButton(
            f"{prefix}{emoji} {display}",
            callback_data=f"mode|{controller.group_id}|{mode_name}"
        )])
    buttons.append([InlineKeyboardButton(
        "Done", callback_data=f"modedone|{controller.group_id}"
    )])
    return InlineKeyboardMarkup(buttons)


async def handle_mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle a game mode."""
    query = update.callback_query
    parts = query.data.split("|")
    group_id = int(parts[1])
    mode_name = parts[2]

    from commands.game_admin import get_game
    controller = get_game(context, group_id)
    if not controller or controller.status != "pre_game_lobby":
        await query.answer(get_message("game_already_started"))
        return
    if not controller.is_game_master(query.from_user.id):
        await query.answer(get_message("gm_only"))
        return

    enabled = controller.toggle_mode(mode_name)
    keyboard = _build_mode_keyboard(controller)
    try:
        await query.edit_message_reply_markup(reply_markup=keyboard)
    except Exception:
        pass
    status = "enabled" if enabled else "disabled"
    await query.answer(f"{mode_name} {status}")


async def handle_mode_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Close mode selection."""
    query = update.callback_query
    parts = query.data.split("|")
    group_id = int(parts[1])

    from commands.game_admin import get_game
    controller = get_game(context, group_id)
    if not controller:
        await query.answer()
        return

    if controller.enabled_modes:
        names = [get_message(f"mode_name_{m}", lang=controller.language) for m in controller.enabled_modes]
        text = msg("active_modes", controller, modes=", ".join(names))
    else:
        text = msg("no_modes", controller)

    try:
        await query.edit_message_text(text)
    except Exception:
        pass
    await query.answer()


# --- Mode phase handlers ---

async def handle_mode_phase(context, controller, group_id, phase):
    """Dispatch to the appropriate mode phase handler."""
    if phase == "investigate":
        await send_investigate(context, controller, group_id)
    elif phase == "loyalty_switch":
        await do_loyalty_switch(context, controller, group_id)
    else:
        # Unknown phase, skip to next mission
        await _advance_to_next_mission(context, controller)


async def send_investigate(context, controller, group_id):
    """Lady of the Lake: holder picks a player to investigate."""
    state = controller.state
    holder_id = state.mode_data.get("lady_holder")
    investigated = state.mode_data.get("investigated", set())
    holder_name = controller.players.get(holder_id, "?")

    # Announce to group
    await context.bot.send_message(
        chat_id=group_id,
        text=msg("lady_announce", controller, holder=holder_name),
        parse_mode="Markdown"
    )

    # Build buttons: all players except holder and already-investigated
    buttons = []
    for uid, name in controller.players.items():
        if uid != holder_id and uid not in investigated:
            buttons.append([InlineKeyboardButton(
                name, callback_data=f"investigate|{group_id}|{uid}"
            )])

    if not buttons:
        # No one left to investigate, skip
        await _advance_to_next_mission(context, controller)
        return

    keyboard = InlineKeyboardMarkup(buttons)
    try:
        await context.bot.send_message(
            chat_id=holder_id,
            text=msg("lady_investigate_prompt", controller),
            reply_markup=keyboard
        )
    except Exception:
        await _advance_to_next_mission(context, controller)

    # Schedule timeout
    schedule_timeout_for_stage(context, controller, "investigate", timeout_investigate)


async def timeout_investigate(context):
    """Auto-investigate a random valid target."""
    group_id = context.job.data
    controller = context.bot_data.get(f"game_{group_id}")
    if not controller or controller.status != "investigate":
        return

    state = controller.state
    holder_id = state.mode_data.get("lady_holder")
    investigated = state.mode_data.get("investigated", set())

    candidates = [uid for uid in controller.players
                  if uid != holder_id and uid not in investigated]
    if not candidates:
        await _advance_to_next_mission(context, controller)
        return

    target_uid = _random.choice(candidates)
    await _resolve_investigate(context, controller, group_id, target_uid)


async def handle_investigate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lady holder picks a target to investigate."""
    query = update.callback_query
    parts = query.data.split("|")
    group_id = int(parts[1])
    target_uid = int(parts[2])

    from commands.game_admin import get_game
    controller = get_game(context, group_id)
    if not controller or controller.status != "investigate":
        await query.answer(get_message("no_active_phase"))
        return

    holder_id = controller.state.mode_data.get("lady_holder")
    if query.from_user.id != holder_id:
        await query.answer(get_message("lady_holder_only"))
        return

    cancel_timeout(context, group_id)

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    await query.answer()

    await _resolve_investigate(context, controller, group_id, target_uid)


async def _resolve_investigate(context, controller, group_id, target_uid):
    """Resolve an investigation: DM result to holder, pass token."""
    state = controller.state
    holder_id = state.mode_data["lady_holder"]
    target_name = controller.players.get(target_uid, "?")
    target_role = state.get_role(target_uid)

    from game.roles import is_evil as _is_evil
    if _is_evil(target_role):
        result_key = "lady_result_evil"
    else:
        result_key = "lady_result_good"

    # DM the result to the holder (private!)
    try:
        await context.bot.send_message(
            chat_id=holder_id,
            text=msg(result_key, controller, name=target_name),
            parse_mode="Markdown"
        )
    except Exception:
        pass

    # Mark investigated, pass token
    state.mode_data.setdefault("investigated", set()).add(target_uid)
    state.mode_data["lady_holder"] = target_uid

    # Announce token pass to group (no result revealed!)
    holder_name = controller.players.get(holder_id, "?")
    await context.bot.send_message(
        chat_id=group_id,
        text=msg("lady_token_passed", controller,
                 old_holder=holder_name, new_holder=target_name),
        parse_mode="Markdown"
    )

    await _advance_to_next_mission(context, controller)


async def do_loyalty_switch(context, controller, group_id):
    """Lancelot: draw a loyalty card and potentially swap Lancelot roles."""
    state = controller.state
    cards = state.mode_data.get("loyalty_cards", [])
    card_index = state.mode_data.get("loyalty_card_index", 0)

    if card_index >= len(cards):
        await _advance_to_next_mission(context, controller)
        return

    card = cards[card_index]
    state.mode_data["loyalty_card_index"] = card_index + 1

    if card == "switch":
        await context.bot.send_message(
            chat_id=group_id,
            text=msg("loyalty_card_switch", controller),
            parse_mode="Markdown"
        )
        # Swap Lancelot roles
        for uid, role in state.player_roles.items():
            if role == "Lancelot_Good":
                state.player_roles[uid] = "Lancelot_Evil"
            elif role == "Lancelot_Evil":
                state.player_roles[uid] = "Lancelot_Good"

        # DM affected players their new role
        for uid, role in state.player_roles.items():
            if role in ("Lancelot_Good", "Lancelot_Evil"):
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=msg("loyalty_switched_role", controller, role=get_role_display_name(role, controller.language)),
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
    else:
        await context.bot.send_message(
            chat_id=group_id,
            text=msg("loyalty_card_no_switch", controller),
            parse_mode="Markdown"
        )

    await _advance_to_next_mission(context, controller)


async def _advance_to_next_mission(context, controller):
    """Move to next mission, with optional discussion phase first."""
    discussion_mins = controller.timeouts.get("discussion", 0)
    if discussion_mins > 0:
        controller.status = "discussion"
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                get_message("discussion_skip_button", lang=controller.language),
                callback_data=f"skipdiscuss|{controller.group_id}"
            )
        ]])
        await context.bot.send_message(
            chat_id=controller.group_id,
            text=msg("discussion_start", controller, minutes=discussion_mins),
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        schedule_timeout_for_stage(context, controller, "discussion", timeout_discussion)
    else:
        await _do_advance(context, controller)


async def handle_skip_discussion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """GM skips the discussion phase early."""
    query = update.callback_query
    parts = query.data.split("|")
    group_id = int(parts[1])

    from commands.game_admin import get_game
    controller = get_game(context, group_id)
    if not controller or controller.status != "discussion":
        await query.answer()
        return

    if not controller.is_game_master(query.from_user.id):
        await query.answer(get_message("gm_only"))
        return

    cancel_timeout(context, group_id)

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    await query.answer()

    await context.bot.send_message(
        chat_id=group_id,
        text=msg("discussion_end", controller),
        parse_mode="Markdown"
    )
    await _do_advance(context, controller)


async def timeout_discussion(context):
    """Discussion phase ended, proceed to next mission."""
    group_id = context.job.data
    controller = context.bot_data.get(f"game_{group_id}")
    if not controller or controller.status != "discussion":
        return
    await context.bot.send_message(
        chat_id=group_id,
        text=msg("discussion_end", controller),
        parse_mode="Markdown"
    )
    await _do_advance(context, controller)


async def _do_advance(context, controller):
    """Actually advance to next mission's team selection."""
    controller.state.next_mission()
    controller.reset_round()
    controller.status = "team_select"
    await send_team_selection(context, controller)


# --- Config command (GM DM) ---

STAGE_LABELS = {
    "lobby": "config_stage_lobby",
    "team_select": "config_stage_team_select",
    "team_vote": "config_stage_team_vote",
    "mission_vote": "config_stage_mission_vote",
    "assassin_guess": "config_stage_assassin",
    "investigate": "config_stage_investigate",
}

TIMEOUT_OPTIONS = [1, 2, 5, 10, 60, 0]  # 0 = no limit


async def config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/config — GM configures per-stage timeouts via DM."""
    from commands.game_admin import get_game
    chat = update.effective_chat
    user = update.effective_user

    # Find the game this GM owns
    controller = None
    if chat.type in ("group", "supergroup"):
        controller = get_game(context, chat.id)
    else:
        # DM — find their game
        for key, c in context.bot_data.items():
            if key.startswith("game_") and hasattr(c, "master_id") and c.master_id == user.id:
                if c.status == "pre_game_lobby":
                    controller = c
                    break

    if not controller:
        await update.message.reply_text(get_message("no_game", context))
        return
    if not controller.is_game_master(user.id):
        await update.message.reply_text(get_message("gm_only", context))
        return

    keyboard = _build_config_keyboard(controller)
    await update.message.reply_text(
        get_message("config_header", lang=controller.language),
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


def _build_config_keyboard(controller):
    lang = controller.language
    buttons = []
    for stage in STAGE_KEYS:
        label = get_message(STAGE_LABELS[stage], lang=lang)
        mins = controller.timeouts.get(stage, 0)
        value = get_message("config_no_limit", lang=lang) if mins == 0 else f"{mins}min"
        buttons.append([InlineKeyboardButton(
            f"{label}: {value}",
            callback_data=f"cfg|{controller.group_id}|{stage}"
        )])
    # Extend toggle
    extend_status = "✅" if controller.allow_extend else "❌"
    buttons.append([InlineKeyboardButton(
        f"{extend_status} {get_message('config_allow_extend', lang=lang)}",
        callback_data=f"cfgext|{controller.group_id}"
    )])
    buttons.append([InlineKeyboardButton(
        get_message("config_done", lang=lang),
        callback_data=f"cfgdone|{controller.group_id}"
    )])
    return InlineKeyboardMarkup(buttons)


async def handle_config_stage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """GM taps a stage to set its timeout."""
    query = update.callback_query
    parts = query.data.split("|")
    group_id = int(parts[1])
    stage = parts[2]

    from commands.game_admin import get_game
    controller = get_game(context, group_id)
    if not controller or not controller.is_game_master(query.from_user.id):
        await query.answer()
        return

    lang = controller.language
    label = get_message(STAGE_LABELS[stage], lang=lang)
    buttons = []
    for mins in TIMEOUT_OPTIONS:
        if mins == 0:
            text = get_message("config_no_limit", lang=lang)
        else:
            text = f"{mins}min"
        buttons.append(InlineKeyboardButton(
            text, callback_data=f"cfgset|{group_id}|{stage}|{mins}"
        ))
    keyboard = InlineKeyboardMarkup([buttons[:3], buttons[3:]])
    try:
        await query.edit_message_text(
            f"{label}:",
            reply_markup=keyboard
        )
    except Exception:
        pass
    await query.answer()


async def handle_config_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """GM sets a specific timeout value for a stage."""
    query = update.callback_query
    parts = query.data.split("|")
    group_id = int(parts[1])
    stage = parts[2]
    mins = int(parts[3])

    from commands.game_admin import get_game
    controller = get_game(context, group_id)
    if not controller or not controller.is_game_master(query.from_user.id):
        await query.answer()
        return

    controller.timeouts[stage] = mins

    # Return to main config view
    keyboard = _build_config_keyboard(controller)
    try:
        await query.edit_message_text(
            get_message("config_header", lang=controller.language),
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except Exception:
        pass
    await query.answer()


async def handle_config_extend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle allow_extend."""
    query = update.callback_query
    parts = query.data.split("|")
    group_id = int(parts[1])

    from commands.game_admin import get_game
    controller = get_game(context, group_id)
    if not controller or not controller.is_game_master(query.from_user.id):
        await query.answer()
        return

    controller.allow_extend = not controller.allow_extend
    keyboard = _build_config_keyboard(controller)
    try:
        await query.edit_message_text(
            get_message("config_header", lang=controller.language),
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except Exception:
        pass
    await query.answer()


async def handle_config_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Close config menu."""
    query = update.callback_query
    parts = query.data.split("|")
    group_id = int(parts[1])

    from commands.game_admin import get_game
    controller = get_game(context, group_id)
    try:
        await query.edit_message_text(get_message("config_saved", lang=controller.language if controller else None))
    except Exception:
        pass
    await query.answer()


# --- Lobby timeout ---

async def schedule_lobby_timeout(context, controller):
    """Schedule lobby expiry."""
    schedule_timeout_for_stage(context, controller, "lobby", timeout_lobby)


async def timeout_lobby(context):
    """Auto-start if enough players, otherwise expire the lobby."""
    group_id = context.job.data
    controller = context.bot_data.get(f"game_{group_id}")
    if not controller or controller.status != "pre_game_lobby":
        return

    if controller.can_start():
        # Auto-start with first available variant
        await context.bot.send_message(
            chat_id=group_id,
            text=get_message("lobby_auto_start", lang=controller.language),
            parse_mode="Markdown"
        )
        from commands.game_admin import _do_start
        await _do_start(context, controller, group_id, 0)
    else:
        await context.bot.send_message(
            chat_id=group_id,
            text=get_message("lobby_expired", lang=controller.language),
            parse_mode="Markdown"
        )
        controller.status = "game_over"
        context.bot_data.pop(f"game_{group_id}", None)


# --- Entry point ---

async def begin_playflow(context: ContextTypes.DEFAULT_TYPE, controller):
    """Called after start_game() succeeds. DMs roles then starts team selection."""
    # Announce which roles are in the game (official rule: players know the role list)
    lang = controller.language
    role_counts = {}
    for r in controller.state.roles:
        role_counts[r] = role_counts.get(r, 0) + 1
    role_list = ", ".join(
        f"{count}x {get_role_display_name(name, lang)}" if count > 1 else get_role_display_name(name, lang)
        for name, count in role_counts.items()
    )
    await context.bot.send_message(
        chat_id=controller.group_id,
        text=msg("roles_in_game", controller, roles=role_list),
        parse_mode="Markdown"
    )

    await dm_assign_roles(context, controller)
    await context.bot.send_message(
        chat_id=controller.group_id,
        text=msg("roles_assigned", controller)
    )
    controller.status = "team_select"
    await send_team_selection(context, controller)


# --- Role helpers ---

def find_game_for_player(context, user_id):
    """Find the active game controller a player is in."""
    for key, controller in context.bot_data.items():
        if key.startswith("game_") and hasattr(controller, "state") and controller.state is not None:
            if user_id in controller.players:
                return controller
    return None


def build_role_message(controller, user_id):
    """Build the role info text for a player."""
    state = controller.state
    lang = controller.language
    role = state.get_role(user_id)
    display_role = get_role_display_name(role, lang)
    lines = [get_message("your_role", lang=lang, role=display_role)]

    vision = get_vision(role, state.player_roles, user_id)
    if vision["sees"] and vision["message_key"]:
        names = [controller.players[uid] for uid in vision["sees"]]
        lines.append(get_message(vision["message_key"], lang=lang,
                                 evil_players=", ".join(names),
                                 targets=", ".join(names)))

    return "\n".join(lines)


# --- Role assignment ---

async def dm_assign_roles(context: ContextTypes.DEFAULT_TYPE, controller):
    """Send each player their role and vision info via DM."""
    for user_id, name in controller.players.items():
        text = build_role_message(controller, user_id)
        try:
            await context.bot.send_message(
                chat_id=user_id, text=text, parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Failed to DM {name} ({user_id}): {e}")
            await context.bot.send_message(
                chat_id=controller.group_id,
                text=msg("dm_failed", controller, name=name)
            )


async def my_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/myrole — player requests their role info (DM only)."""
    if update.effective_chat.type != "private":
        await update.message.reply_text(get_message("myrole_dm_only", context))
        return
    user_id = update.effective_user.id
    controller = find_game_for_player(context, user_id)
    if not controller:
        await update.message.reply_text(get_message("not_in_game", context))
        return
    await update.message.reply_text(
        build_role_message(controller, user_id), parse_mode="Markdown"
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start — welcome message, auto-send role if in an active game."""
    user_id = update.effective_user.id
    controller = find_game_for_player(context, user_id)
    if controller:
        await update.message.reply_text(
            build_role_message(controller, user_id), parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            get_message("welcome_dm", context)
        )


# --- Team selection ---

def build_team_keyboard(controller):
    """Build inline keyboard for team selection."""
    buttons = []
    for uid, name in controller.players.items():
        prefix = "✅ " if uid in controller.selected_team else ""
        buttons.append([InlineKeyboardButton(
            f"{prefix}{name}",
            callback_data=f"team_{controller.group_id}_{uid}"
        )])
    buttons.append([InlineKeyboardButton(
        get_message("confirm_team_button", lang=controller.language,
                    current=len(controller.selected_team),
                    size=controller.state.get_team_size()),
        callback_data=f"teamconfirm_{controller.group_id}"
    )])
    return InlineKeyboardMarkup(buttons)


def build_mission_tracker(state):
    """Build a visual mission tracker string."""
    symbols = []
    for i in range(1, 6):
        if i < state.mission_number:
            entry = state.mission_history[i - 1]
            symbols.append("✅" if entry["result"] == "success" else "❌")
        elif i == state.mission_number:
            symbols.append("⏳")
        else:
            symbols.append("⚪")
    return " ".join(symbols)


async def send_team_selection(context: ContextTypes.DEFAULT_TYPE, controller):
    """Post the team selection keyboard in the group chat."""
    state = controller.state
    leader_name = controller.players[state.get_current_leader()]
    team_size = state.get_team_size()
    tracker = build_mission_tracker(state)

    text = msg("team_select_header", controller,
               mission=state.mission_number, tracker=tracker,
               leader=leader_name, size=team_size)

    if state.failed_vote_count > 0:
        text += "\n" + msg("failed_proposals_warning", controller, count=state.failed_vote_count)

    keyboard = build_team_keyboard(controller)
    m = await context.bot.send_message(
        chat_id=controller.group_id,
        text=text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    controller.team_message_id = m.message_id

    # DM the leader a turn notification
    leader_id = state.get_current_leader()
    try:
        await context.bot.send_message(
            chat_id=leader_id,
            text=msg("turn_notification", controller,
                     mission=state.mission_number, size=team_size),
            parse_mode="Markdown"
        )
    except Exception:
        pass

    # Schedule timeout for team selection
    schedule_timeout_for_stage(context, controller, "team_select", timeout_team_select)


async def timeout_team_select(context: ContextTypes.DEFAULT_TYPE):
    """Auto-select team and confirm if leader hasn't acted in time."""
    group_id = context.job.data
    controller = context.bot_data.get(f"game_{group_id}")
    if not controller or controller.status != "team_select":
        return

    state = controller.state
    needed = state.get_team_size()

    # Fill remaining team slots randomly
    available = [uid for uid in controller.players if uid not in controller.selected_team]
    while len(controller.selected_team) < needed and available:
        pick = _random.choice(available)
        available.remove(pick)
        controller.selected_team.append(pick)

    await context.bot.send_message(
        chat_id=group_id,
        text=msg("timeout_auto_action", controller),
        parse_mode="Markdown"
    )

    # Remove old keyboard
    if controller.team_message_id:
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=group_id, message_id=controller.team_message_id, reply_markup=None)
        except Exception:
            pass

    # Proceed to team vote
    team_names = [controller.players[uid] for uid in controller.selected_team]
    leader_name = controller.players[state.get_current_leader()]
    controller.status = "team_vote"
    await context.bot.send_message(
        chat_id=group_id,
        text=msg("team_proposed", controller,
                 leader=leader_name, team=", ".join(team_names)),
        parse_mode="Markdown"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(btn("approve", controller),
                                 callback_data=f"teamvote_{group_id}_approve"),
            InlineKeyboardButton(btn("reject", controller),
                                 callback_data=f"teamvote_{group_id}_reject"),
        ]
    ])
    for uid, name in controller.players.items():
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=msg("team_vote_prompt", controller, team=", ".join(team_names)),
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        except Exception:
            pass

    schedule_timeout_for_stage(context, controller, "team_vote", timeout_team_vote)


async def handle_team_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Leader toggles a player on/off the team."""
    query = update.callback_query
    controller, group_id = get_game_from_callback(context, query.data, "team")

    if not controller or controller.status != "team_select":
        await query.answer(get_message("no_active_phase"))
        return

    if query.from_user.id != controller.state.get_current_leader():
        await query.answer(msg("not_leader", controller))
        return

    target_uid = int(query.data.split("_")[-1])
    controller.toggle_team_member(target_uid)

    keyboard = build_team_keyboard(controller)
    try:
        await query.edit_message_reply_markup(reply_markup=keyboard)
    except Exception:
        pass
    await query.answer()


async def handle_team_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Leader confirms the selected team."""
    query = update.callback_query
    controller, group_id = get_game_from_callback(context, query.data, "teamconfirm")

    if not controller or controller.status != "team_select":
        await query.answer(get_message("no_active_phase"))
        return

    if query.from_user.id != controller.state.get_current_leader():
        await query.answer(msg("not_leader", controller))
        return

    if not controller.is_team_complete():
        team_size = controller.state.get_team_size()
        await query.answer(msg("team_size_error", controller, size=team_size))
        return

    cancel_timeout(context, group_id)

    # Lock in the team - remove keyboard
    team_names = [controller.players[uid] for uid in controller.selected_team]
    leader_name = controller.players[controller.state.get_current_leader()]
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    # Announce the proposed team
    controller.status = "team_vote"
    await context.bot.send_message(
        chat_id=group_id,
        text=msg("team_proposed", controller,
                 leader=leader_name, team=", ".join(team_names)),
        parse_mode="Markdown"
    )

    # DM each player with approve/reject buttons
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(btn("approve", controller),
                                 callback_data=f"teamvote_{group_id}_approve"),
            InlineKeyboardButton(btn("reject", controller),
                                 callback_data=f"teamvote_{group_id}_reject"),
        ]
    ])
    for uid, name in controller.players.items():
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=msg("team_vote_prompt", controller, team=", ".join(team_names)),
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Failed to DM {name} for team vote: {e}")

    # Schedule timeout for team vote
    schedule_timeout_for_stage(context, controller, "team_vote", timeout_team_vote)

    await query.answer()


# --- Team voting ---

async def handle_team_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """A player votes approve/reject on the proposed team."""
    query = update.callback_query
    controller, group_id = get_game_from_callback(context, query.data, "teamvote")

    if not controller or controller.status != "team_vote":
        await query.answer(get_message("no_active_phase"))
        return

    user_id = query.from_user.id
    if user_id not in controller.players:
        await query.answer(get_message("not_in_game"))
        return
    if user_id in controller.team_votes:
        await query.answer(msg("already_voted", controller))
        return

    vote = query.data.split("_")[-1]
    approve = vote == "approve"
    controller.record_team_vote(user_id, approve)

    vote_text = btn("approve", controller) if approve else btn("reject", controller)
    try:
        await query.edit_message_text(msg("team_vote_recorded", controller, vote=vote_text))
    except Exception:
        pass
    await query.answer()

    # Send progress to group
    await context.bot.send_message(
        chat_id=group_id,
        text=msg("votes_progress", controller,
                 count=len(controller.team_votes), total=len(controller.players))
    )

    if controller.all_team_votes_in():
        cancel_timeout(context, group_id)
        await resolve_team_vote(context, controller, group_id)


async def timeout_team_vote(context: ContextTypes.DEFAULT_TYPE):
    """Auto-vote for players who haven't voted on the team."""
    group_id = context.job.data
    controller = context.bot_data.get(f"game_{group_id}")
    if not controller or controller.status != "team_vote":
        return

    await context.bot.send_message(
        chat_id=group_id,
        text=msg("timeout_auto_action", controller),
        parse_mode="Markdown"
    )

    # Auto-vote randomly for missing voters
    for uid in controller.players:
        if uid not in controller.team_votes:
            controller.record_team_vote(uid, _random.choice([True, False]))

    await resolve_team_vote(context, controller, group_id)


async def resolve_team_vote(context, controller, group_id):
    """Process the team vote results."""
    votes = list(controller.team_votes.values())
    leader_id = controller.state.get_current_leader()
    mission_num = controller.state.mission_number
    approved = controller.state.process_vote(votes)

    # Save vote history for /detailhistory
    controller.vote_history.append({
        "mission": mission_num,
        "leader": leader_id,
        "team": list(controller.selected_team),
        "votes": dict(controller.team_votes),
        "approved": approved,
    })

    lines = [msg("team_vote_results", controller)]
    for uid, vote in controller.team_votes.items():
        name = controller.players[uid]
        emoji = "👍" if vote else "👎"
        lines.append(f"  {emoji} {name}")

    approve_count = votes.count(True)
    reject_count = votes.count(False)
    lines.append(f"\n{btn('approve', controller)}: {approve_count} | {btn('reject', controller)}: {reject_count}")

    if approved:
        lines.append("\n" + msg("team_approved", controller))
        await context.bot.send_message(
            chat_id=group_id, text="\n".join(lines), parse_mode="Markdown"
        )
        controller.status = "mission_vote"
        await send_mission_vote(context, controller, group_id)
    else:
        lines.append("\n" + msg("team_rejected", controller,
                                failed_count=controller.state.failed_vote_count))
        await context.bot.send_message(
            chat_id=group_id, text="\n".join(lines), parse_mode="Markdown"
        )

        if controller.state.failed_vote_count >= 5:
            await end_of_game(controller, context, group_id)
        else:
            controller.reset_round()
            controller.status = "team_select"
            await send_team_selection(context, controller)


# --- Mission voting ---

async def send_mission_vote(context, controller, group_id):
    """DM team members with success/fail buttons."""
    for uid in controller.selected_team:
        name = controller.players.get(uid, "Unknown")
        is_evil = controller.state.is_evil(uid)

        if is_evil:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(btn("success", controller),
                                         callback_data=f"missionvote_{group_id}_success"),
                    InlineKeyboardButton(btn("fail", controller),
                                         callback_data=f"missionvote_{group_id}_fail"),
                ]
            ])
        else:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(btn("success", controller),
                                      callback_data=f"missionvote_{group_id}_success")]
            ])

        try:
            await context.bot.send_message(
                chat_id=uid,
                text=msg("mission_vote_prompt", controller),
                reply_markup=keyboard
            )
        except Exception as e:
            print(f"Failed to DM {name} for mission vote: {e}")

    # Schedule timeout for mission vote
    schedule_timeout_for_stage(context, controller, "mission_vote", timeout_mission_vote)


async def timeout_mission_vote(context: ContextTypes.DEFAULT_TYPE):
    """Auto-vote for team members who haven't voted on the mission."""
    group_id = context.job.data
    controller = context.bot_data.get(f"game_{group_id}")
    if not controller or controller.status != "mission_vote":
        return

    await context.bot.send_message(
        chat_id=group_id,
        text=msg("timeout_auto_action", controller),
        parse_mode="Markdown"
    )

    # Auto-vote: good=success, evil=random
    for uid in controller.selected_team:
        if uid not in controller.mission_votes:
            if controller.state.is_evil(uid):
                controller.record_mission_vote(uid, _random.choice([True, False]))
            else:
                controller.record_mission_vote(uid, True)

    if _has_excalibur(controller):
        await send_excalibur(context, controller, group_id)
    else:
        await resolve_mission(context, controller, group_id)


async def handle_mission_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """A team member votes success/fail on the mission."""
    query = update.callback_query
    controller, group_id = get_game_from_callback(context, query.data, "missionvote")

    if not controller or controller.status != "mission_vote":
        await query.answer(get_message("no_active_phase"))
        return

    user_id = query.from_user.id
    if user_id not in controller.selected_team:
        await query.answer(get_message("not_on_team"))
        return
    if user_id in controller.mission_votes:
        await query.answer(msg("already_voted", controller))
        return

    vote = query.data.split("_")[-1]
    success = vote == "success"

    if not controller.state.is_evil(user_id) and not success:
        await query.answer(msg("good_must_success", controller))
        return

    controller.record_mission_vote(user_id, success)

    vote_text = btn("success", controller) if success else btn("fail", controller)
    try:
        await query.edit_message_text(msg("mission_vote_recorded", controller, vote=vote_text))
    except Exception:
        pass
    await query.answer()

    if controller.all_mission_votes_in():
        cancel_timeout(context, group_id)
        # Check for Excalibur before revealing results
        if _has_excalibur(controller):
            await send_excalibur(context, controller, group_id)
        else:
            await resolve_mission(context, controller, group_id)


def _has_excalibur(controller) -> bool:
    return any(m.name == "excalibur" for m in controller.active_modes)


async def send_excalibur(context, controller, group_id):
    """Leader picks one team member to flip their mission vote."""
    controller.status = "excalibur"
    leader_id = controller.state.get_current_leader()
    leader_name = controller.players[leader_id]

    await context.bot.send_message(
        chat_id=group_id,
        text=msg("excalibur_announce", controller, leader=leader_name),
        parse_mode="Markdown"
    )

    buttons = []
    for uid in controller.selected_team:
        name = controller.players[uid]
        buttons.append([InlineKeyboardButton(
            name, callback_data=f"excalibur|{group_id}|{uid}"
        )])
    # Option to skip
    buttons.append([InlineKeyboardButton(
        get_message("excalibur_skip", lang=controller.language),
        callback_data=f"excalibur|{group_id}|skip"
    )])

    keyboard = InlineKeyboardMarkup(buttons)
    try:
        await context.bot.send_message(
            chat_id=leader_id,
            text=msg("excalibur_prompt", controller),
            reply_markup=keyboard
        )
    except Exception:
        # Can't DM leader, skip excalibur
        await resolve_mission(context, controller, group_id)
        return

    schedule_timeout_for_stage(context, controller, "mission_vote", timeout_excalibur)


async def timeout_excalibur(context):
    """Leader didn't use Excalibur in time, skip it."""
    group_id = context.job.data
    controller = context.bot_data.get(f"game_{group_id}")
    if not controller or controller.status != "excalibur":
        return
    await context.bot.send_message(
        chat_id=group_id,
        text=msg("timeout_auto_action", controller),
        parse_mode="Markdown"
    )
    await resolve_mission(context, controller, group_id)


async def handle_excalibur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Leader picks a team member to flip their vote, or skips."""
    query = update.callback_query
    parts = query.data.split("|")
    group_id = int(parts[1])
    target = parts[2]

    from commands.game_admin import get_game
    controller = get_game(context, group_id)
    if not controller or controller.status != "excalibur":
        await query.answer(get_message("no_active_phase"))
        return

    if query.from_user.id != controller.state.get_current_leader():
        await query.answer(get_message("not_leader"))
        return

    cancel_timeout(context, group_id)

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    await query.answer()

    if target != "skip":
        target_uid = int(target)
        target_name = controller.players.get(target_uid, "?")
        # Flip the vote
        if target_uid in controller.mission_votes:
            controller.mission_votes[target_uid] = not controller.mission_votes[target_uid]

        await context.bot.send_message(
            chat_id=group_id,
            text=msg("excalibur_used", controller, leader=controller.players[controller.state.get_current_leader()], target=target_name),
            parse_mode="Markdown"
        )
    else:
        await context.bot.send_message(
            chat_id=group_id,
            text=msg("excalibur_skipped", controller),
            parse_mode="Markdown"
        )

    await resolve_mission(context, controller, group_id)


async def resolve_mission(context, controller, group_id):
    """Process mission results."""
    state = controller.state
    fails = list(controller.mission_votes.values()).count(False)
    success = state.is_mission_successful(fails)
    state.record_mission(controller.selected_team, success)

    tracker = build_mission_tracker(state)
    if success:
        text = msg("mission_success", controller,
                   mission=state.mission_number - 1, fails=fails, tracker=tracker)
    else:
        text = msg("mission_fail", controller,
                   mission=state.mission_number - 1, fails=fails, tracker=tracker)

    await context.bot.send_message(
        chat_id=group_id, text=text, parse_mode="Markdown"
    )

    if state.is_game_over():
        await end_of_game(controller, context, group_id)
    else:
        # Check if any mode wants to inject a phase before next mission
        completed_mission = state.mission_number  # mission just completed (not yet incremented)
        injected_phase = controller.check_mode_phases(completed_mission)
        if injected_phase:
            controller.status = injected_phase
            await handle_mode_phase(context, controller, group_id, injected_phase)
        else:
            await _advance_to_next_mission(context, controller)


# --- End of game ---

async def end_of_game(controller, context, group_id):
    """Handle end-of-game logic including assassin phase."""
    state = controller.state

    if state.failed_vote_count >= 5:
        await context.bot.send_message(
            chat_id=group_id,
            text=msg("five_rejects", controller),
            parse_mode="Markdown"
        )
        await game_summary(controller, context, group_id)
        await dm_end_results(controller, context, "evil", "end_reason_five_rejects")
        await reset_lobby(controller, context)
        return

    if state.failed_missions >= 3:
        await context.bot.send_message(
            chat_id=group_id,
            text=msg("evil_wins", controller),
            parse_mode="Markdown"
        )
        await game_summary(controller, context, group_id)
        await dm_end_results(controller, context, "evil", "end_reason_missions")
        await reset_lobby(controller, context)
        return

    if state.successful_missions >= 3:
        if state.is_assassin_present():
            controller.status = "assassin_guess"
            await context.bot.send_message(
                chat_id=group_id,
                text=msg("assassin_phase", controller),
                parse_mode="Markdown"
            )
            await send_assassin_guess(context, controller, group_id)
        else:
            await context.bot.send_message(
                chat_id=group_id,
                text=msg("good_wins", controller),
                parse_mode="Markdown"
            )
            await game_summary(controller, context, group_id)
            await dm_end_results(controller, context, "good", "end_reason_missions")
            await reset_lobby(controller, context)


# --- Assassin guess ---

async def send_assassin_guess(context, controller, group_id):
    """DM the assassin with buttons to guess Merlin."""
    assassin_id = controller.state.get_assassin()
    good_players = controller.state.get_good_players()

    buttons = []
    for uid in good_players:
        name = controller.players[uid]
        buttons.append([InlineKeyboardButton(
            name, callback_data=f"assassin_{group_id}_{uid}"
        )])

    keyboard = InlineKeyboardMarkup(buttons)
    try:
        await context.bot.send_message(
            chat_id=assassin_id,
            text=msg("assassin_prompt", controller),
            reply_markup=keyboard
        )
    except Exception as e:
        print(f"Failed to DM assassin: {e}")
        await context.bot.send_message(
            chat_id=group_id,
            text=msg("assassin_unreachable", controller),
            parse_mode="Markdown"
        )
        await game_summary(controller, context, group_id)
        await dm_end_results(controller, context, "good", "end_reason_assassin_unreachable")
        await reset_lobby(controller, context)
        return

    # Schedule timeout for assassin guess
    schedule_timeout_for_stage(context, controller, "assassin_guess", timeout_assassin_guess)


async def timeout_assassin_guess(context: ContextTypes.DEFAULT_TYPE):
    """Auto-guess randomly if assassin doesn't act in time."""
    group_id = context.job.data
    controller = context.bot_data.get(f"game_{group_id}")
    if not controller or controller.status != "assassin_guess":
        return

    good_players = controller.state.get_good_players()
    target_uid = _random.choice(good_players)
    target_name = controller.players.get(target_uid, "Unknown")

    await context.bot.send_message(
        chat_id=group_id,
        text=msg("timeout_auto_action", controller),
        parse_mode="Markdown"
    )

    if controller.state.get_role(target_uid) == "Merlin":
        await context.bot.send_message(
            chat_id=group_id,
            text=msg("assassin_correct", controller, target=target_name),
            parse_mode="Markdown"
        )
        await game_summary(controller, context, group_id)
        await dm_end_results(controller, context, "evil", "end_reason_assassin_correct")
    else:
        merlin_id = controller.state.get_merlin()
        merlin_name = controller.players.get(merlin_id, "Unknown")
        await context.bot.send_message(
            chat_id=group_id,
            text=msg("assassin_wrong", controller, target=target_name, merlin=merlin_name),
            parse_mode="Markdown"
        )
        await game_summary(controller, context, group_id)
        await dm_end_results(controller, context, "good", "end_reason_assassin_wrong")

    await reset_lobby(controller, context)


async def handle_assassin_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Assassin picks a player as their Merlin guess."""
    query = update.callback_query
    controller, group_id = get_game_from_callback(context, query.data, "assassin")

    if not controller or controller.status != "assassin_guess":
        await query.answer(get_message("no_active_phase"))
        return

    if query.from_user.id != controller.state.get_assassin():
        await query.answer(get_message("assassin_only"))
        return

    cancel_timeout(context, group_id)

    target_uid = int(query.data.split("_")[-1])
    target_name = controller.players.get(target_uid, "Unknown")

    try:
        await query.edit_message_text(msg("assassin_you_guessed", controller, target=target_name))
    except Exception:
        pass
    await query.answer()

    if controller.state.get_role(target_uid) == "Merlin":
        await context.bot.send_message(
            chat_id=group_id,
            text=msg("assassin_correct", controller, target=target_name),
            parse_mode="Markdown"
        )
        await game_summary(controller, context, group_id)
        await dm_end_results(controller, context, "evil", "end_reason_assassin_correct")
    else:
        merlin_id = controller.state.get_merlin()
        merlin_name = controller.players.get(merlin_id, "Unknown")
        await context.bot.send_message(
            chat_id=group_id,
            text=msg("assassin_wrong", controller, target=target_name, merlin=merlin_name),
            parse_mode="Markdown"
        )
        await game_summary(controller, context, group_id)
        await dm_end_results(controller, context, "good", "end_reason_assassin_wrong")

    await reset_lobby(controller, context)


# --- Role descriptions ---

async def roles_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/roles — list all roles and their descriptions."""
    # Use game language if in a game, else context language
    controller = _get_controller_from_update(update, context)
    lang = controller.language if controller else None

    from game.roles import ROLE_REGISTRY
    lines = [get_message("roles_list_header", lang=lang)]
    for role_name, info in ROLE_REGISTRY.items():
        alignment = info["alignment"]
        side = "😇" if alignment == "good" else "😈"
        desc = get_message(f"role_desc_{role_name}", lang=lang)
        display = get_role_display_name(role_name, lang)
        lines.append(f"  {side} **{display}** — {desc}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# --- In-game history commands ---

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/history — show mission results so far."""
    controller = _get_controller_from_update(update, context)
    if not controller or not controller.state:
        await update.message.reply_text(get_message("no_game", context))
        return

    state = controller.state
    if not state.mission_history:
        await update.message.reply_text(get_message("no_missions_yet", lang=controller.language))
        return

    tracker = build_mission_tracker(state)
    lines = [f"{get_message('mission_history_header', lang=controller.language)} | {tracker}"]
    for m in state.mission_history:
        result = "✅" if m["result"] == "success" else "❌"
        team = ", ".join(controller.players.get(uid, "?") for uid in m["team"])
        leader = controller.players.get(m["leader"], "?")
        lines.append(f"  Mission {m['mission']}: {result} | Leader: {leader} | Team: {team}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def vote_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/votehistory — show all team proposals and vote details."""
    controller = _get_controller_from_update(update, context)
    if not controller or not controller.state:
        await update.message.reply_text(get_message("no_game", context))
        return

    if not controller.vote_history:
        await update.message.reply_text(get_message("no_votes_yet", lang=controller.language))
        return

    lang = controller.language if controller else None
    lines = [get_message("vote_history_header", lang=lang)]
    for i, entry in enumerate(controller.vote_history, 1):
        leader = controller.players.get(entry["leader"], "?")
        team = ", ".join(controller.players.get(uid, "?") for uid in entry["team"])
        status = get_message("vote_approved", lang=lang) if entry["approved"] else get_message("vote_rejected", lang=lang)
        lines.append(f"\n**#{i}** (Mission {entry['mission']}) | {status}")
        lines.append(f"  Leader: {leader} | Team: {team}")
        for uid, vote in entry["votes"].items():
            name = controller.players.get(uid, "?")
            emoji = "👍" if vote else "👎"
            lines.append(f"    {emoji} {name}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


def _get_controller_from_update(update, context):
    """Get controller from group chat or player's active game."""
    chat = update.effective_chat
    if chat.type in ("group", "supergroup"):
        from commands.game_admin import get_game
        return get_game(context, chat.id)
    else:
        return find_game_for_player(context, update.effective_user.id)


# --- Abort game ---

async def abort_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/abort — game master ends the game immediately."""
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text(get_message("use_in_group", context))
        return

    from commands.game_admin import get_game
    controller = get_game(context, chat.id)
    if not controller:
        await update.message.reply_text(get_message("no_game", context))
        return

    if not controller.is_game_master(update.effective_user.id):
        await update.message.reply_text(get_message("gm_only", context))
        return

    cancel_timeout(context, controller.group_id)
    await context.bot.send_message(
        chat_id=chat.id,
        text=msg("game_aborted", controller),
        parse_mode="Markdown"
    )
    if controller.state:
        await game_summary(controller, context, chat.id)
    await reset_lobby(controller, context)


# --- Game summary and cleanup ---

async def game_summary(controller, context, group_id):
    """Show all roles and mission history."""
    lang = controller.language
    lines = [get_message("game_summary_roles", lang=lang)]
    for user_id, role in controller.state.player_roles.items():
        name = controller.players.get(user_id, "Unknown")
        side = get_message("side_evil", lang=lang) if is_evil_role(role) else get_message("side_good", lang=lang)
        lines.append(f"  {name}: {get_role_display_name(role, lang)} ({side})")

    if controller.state.mission_history:
        lines.append("\n" + get_message("game_summary_missions", lang=lang))
        for mission in controller.state.mission_history:
            team = ", ".join(controller.players.get(uid, "?") for uid in mission["team"])
            leader = controller.players.get(mission["leader"], "?")
            result = "✅" if mission["result"] == "success" else "❌"
            lines.append(f"  Mission {mission['mission']}: {result} | Leader: {leader} | Team: {team}")

    await context.bot.send_message(
        chat_id=group_id,
        text="\n".join(lines),
        parse_mode="Markdown"
    )


async def dm_end_results(controller, context, winner: str, reason: str):
    """DM each player whether they won or lost and why. Also record stats."""
    lang = controller.language
    state = controller.state
    reason_text = get_message(reason, lang=lang)

    # Update persistent stats in chat_data
    chat_data = context.bot_data.get(f"_chatdata_{controller.group_id}")
    # chat_data may not be available here; use a helper stored on controller
    stats = context.bot_data.setdefault(f"stats_{controller.group_id}", {})

    for uid, name in controller.players.items():
        role = state.get_role(uid)
        player_side = "evil" if is_evil_role(role) else "good"
        won = player_side == winner

        # Record stats
        player_stats = stats.setdefault(str(uid), {"name": name, "wins": 0, "losses": 0, "games": 0})
        player_stats["name"] = name  # update name in case it changed
        player_stats["games"] += 1
        if won:
            player_stats["wins"] += 1
            text = get_message("dm_you_won", lang=lang, role=get_role_display_name(role, lang), reason=reason_text)
        else:
            player_stats["losses"] += 1
            text = get_message("dm_you_lost", lang=lang, role=get_role_display_name(role, lang), reason=reason_text)

        try:
            await context.bot.send_message(chat_id=uid, text=text, parse_mode="Markdown")
        except Exception:
            pass


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/stats — show win/loss leaderboard for this group."""
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text(get_message("use_in_group", context))
        return

    stats = context.bot_data.get(f"stats_{chat.id}", {})
    if not stats:
        await update.message.reply_text(get_message("no_stats", context))
        return

    # Sort by win rate (min 1 game), then by total wins
    entries = sorted(
        stats.values(),
        key=lambda s: (s["wins"] / max(s["games"], 1), s["wins"]),
        reverse=True
    )

    lang = None
    from commands.game_admin import get_game
    controller = get_game(context, chat.id)
    if controller:
        lang = controller.language

    lines = [get_message("stats_header", lang=lang)]
    for i, s in enumerate(entries, 1):
        rate = round(s["wins"] / max(s["games"], 1) * 100)
        lines.append(f"  {i}. **{s['name']}** — {s['wins']}W/{s['losses']}L ({rate}%) [{s['games']} games]")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def reset_lobby(controller, context):
    """Remove the game from bot_data."""
    controller.status = "game_over"
    context.bot_data.pop(f"game_{controller.group_id}", None)
