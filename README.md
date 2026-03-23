# Avalon Telegram Bot

An open-source, self-hosted Telegram bot for playing **The Resistance: Avalon** in group chats. Supports 5-10 players with full game flow, multiple game modes, and i18n.

## Features

### Core Game
- Full Avalon game flow: team selection, team voting, mission voting, assassin guess
- Official role compositions for 5-10 players
- Custom role compositions — GM picks any combination of roles
- Role variant selection when multiple presets are available
- Roles announced at game start (official rule)
- Role assignment via DM with vision info (Merlin sees evil, etc.)

### Game Modes
- **Lady of the Lake** — After missions 2-4, a player investigates another's loyalty
- **Lancelot** — Loyalty cards may switch Lancelot players mid-game (official card-based rules)
- **Excalibur** — After mission votes, the leader can flip one team member's vote
- Modes are toggled by GM via `/mode` before starting

### Timeout System
- Per-stage configurable timeouts (lobby, team select, vote, mission, assassin, investigation, discussion)
- Quick speed presets: Fast (2min), Medium (5min), Slow (30min), No Limit
- Fine-grained control via `/timeoutconfig`
- 30-second warning with optional player-extendable "+2 min" button
- Lobby auto-starts if enough players when timer expires, otherwise expires
- Auto-action for inactive players (random vote, random team selection)

### Discussion Phase
- Optional timed discussion between missions
- GM can skip early via inline button
- Configurable duration per `/timeoutconfig`

### Internationalization (i18n)
- Full support for **English** and **Traditional Chinese** (zh-TW)
- All messages, buttons, role names, and mode names are translatable
- Per-group language setting (persistent across games)
- GM sets language via `/language`
- Easy to add new languages: copy `languages/en/` to `languages/{code}/` and translate

### Other Features
- `/roles` — List all roles with descriptions
- `/myrole` — Check your role anytime (DM only)
- `/history` — View mission results
- `/votehistory` — View detailed team proposal and vote history
- `/stats` — Persistent win/loss leaderboard per group
- `/kick` — GM kicks players via inline buttons
- `/abort` — GM ends the game immediately
- Turn notification DMs to the current leader
- Win/loss result DMs to all players at game end
- Game statistics tracked across games per group

## Requirements

- **Python 3.10+**
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## Setup

```bash
# Clone the repo
git clone https://github.com/VTT99/Avalon-Telegram-bot.git
cd Avalon-Telegram-bot

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Configure bot token
echo "BOT_TOKEN=your_token_here" > .env

# Run the bot
python main.py              # Normal mode (5-10 players)
python main.py --debug      # Debug mode (2-10 players, for testing)
```

## Commands

| Command | Who | Description |
|---------|-----|-------------|
| `/newgame` | Anyone | Create a new game in a group |
| `/join` | Anyone | Join the current game |
| `/leave` | Anyone | Leave the current game |
| `/startgame` | GM | Start the game (shows variant/custom picker) |
| `/abort` | GM | End the game immediately |
| `/kick` | GM | Kick a player (inline buttons) |
| `/speed` | GM | Quick speed preset (Fast/Medium/Slow/None) |
| `/timeoutconfig` | GM | Configure per-stage timeouts |
| `/mode` | GM | Toggle game modes (Lady/Lancelot/Excalibur) |
| `/language` | GM | Set group language |
| `/myrole` | Player | Check your role (DM only) |
| `/roles` | Anyone | List all roles and descriptions |
| `/history` | Anyone | View mission history |
| `/votehistory` | Anyone | View detailed vote history |
| `/stats` | Anyone | View win/loss leaderboard |

## Architecture

```
main.py                     # Entry point, handler registration
commands/
  game_admin.py             # /newgame, /startgame, variant/custom selection
  game_playflow.py          # All game flow handlers, timeouts, modes
  pre_game_actions.py       # /join, /leave, /kick
  language.py               # /language command
game/
  game_controller.py        # Controller class (lobby, modes, round tracking)
  game_state.py             # State class (missions, votes, roles)
  game_modes.py             # GameMode base class + Lady/Lancelot/Excalibur
  roles.py                  # Role registry, alignment, vision logic
conf/
  game_setting.toml         # Normal mode: 5-10 player configs
  game_setting_debug.toml   # Debug mode: 2-10 player configs
  roles.toml                # Role metadata (alignment, description)
  game_modes.toml           # Mode display metadata
  game_setting.py           # Config loader (switches on AVALON_DEBUG env)
utils/
  language.py               # i18n message loading with fallback
  message_helper.py         # Player list formatting
languages/
  en/message.toml           # English messages
  en/button.toml            # English button labels
  zh-TW/message.toml        # Traditional Chinese messages
  zh-TW/button.toml         # Traditional Chinese button labels
```

### Key Design Decisions

- **Callback-based flow** (not ConversationHandler) — supports cross-chat DM voting
- **Role registry in TOML** — metadata only; visibility logic in Python (`game/roles.py`)
- **Game modes as Python classes** — `GameMode` base class with hooks (`modify_roles`, `on_mission_end`)
- **Per-group persistent language** — stored in `chat_data`, survives across games
- **PicklePersistence** — all game state persists across bot restarts

## Adding a New Language

1. Copy `languages/en/` to `languages/{your_code}/`
2. Translate all keys in `message.toml` and `button.toml`
3. Add the language code to `languages` array in `conf/game_setting.toml`
4. Add a button for it in `commands/language.py`

## Adding a New Game Mode

1. Create a class in `game/game_modes.py` extending `GameMode`
2. Implement hooks: `modify_roles()`, `on_game_start()`, `on_mission_end()`
3. Register in `MODE_CLASSES` dict
4. Add display metadata to `conf/game_modes.toml`
5. Add `mode_name_{name}` to message files
6. Add phase handlers in `game_playflow.py` if the mode injects phases

## License

Open source. Self-host and modify freely.
