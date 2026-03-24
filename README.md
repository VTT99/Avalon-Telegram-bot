# Avalon Telegram Bot

> **Status: Early Development / Testing** — The bot is functional but actively being developed. Expect bugs, breaking changes, and missing polish. Contributions and bug reports welcome!

A **free, open-source, self-hosted** Telegram bot for playing [The Resistance: Avalon](https://indieboardsandcards.com/index.php/our-games/the-resistance-avalon/) in group chats. Fully customizable — configure roles, game modes, timeouts, and language to fit your group's play style.

## Why Self-Host?

- **Free forever** — no subscriptions, no ads, no data collection
- **Full control** — customize rules, roles, timeouts, and translations
- **Privacy** — your game data stays on your server
- **Extensible** — add new game modes, roles, or languages with minimal code

## Features

### Core Game
- Complete Avalon game flow: team selection, team voting, mission voting, assassin guess
- Official role compositions for 5-10 players
- **Custom role compositions** — GM picks any combination of roles via DM
- Role variant selection when multiple presets are available
- Role list announced at game start (official rule)
- Role assignment via DM with vision info, alignment indicator, and gameplay tips

### Game Modes
- **Lady of the Lake** — After missions 2-4, investigate a player's loyalty
- **Lancelot** — Loyalty cards may switch Lancelot players mid-game (official card-based rules)
- **Excalibur** — After mission votes, the leader can flip one team member's vote
- Toggle modes via `/mode` before starting

### Timeout & Pacing
- Per-stage configurable timeouts (lobby, team select, vote, mission, assassin, investigation, discussion)
- Quick speed presets: Fast / Medium / Slow / No Limit
- Fine-grained control via `/timeoutconfig`
- 30-second warning with optional player-extendable "+2 min" button
- Lobby auto-starts when timer expires (if enough players), otherwise expires
- Auto-action for inactive players (random vote, random team selection)

### Discussion Phase
- Optional timed discussion between missions for debate
- GM can skip early via inline button
- Disabled by default, configurable duration

### Internationalization (i18n)
- Full support for **English** and **Traditional Chinese** (zh-TW)
- Everything is translatable: messages, buttons, role names, mode names, gameplay tips
- Per-group persistent language setting (survives across games)
- Easy to add new languages (see guide below)

### Player Experience
- `/roles` — Interactive role guide with descriptions and gameplay tips
- `/myrole` — Check your role anytime via DM
- `/history` — View mission results
- `/votehistory` — View detailed team proposal and vote history
- `/stats` — Persistent win/loss leaderboard per group
- Turn notification DMs to the current leader
- Win/loss result DMs with role reveal to all players at game end

## Requirements

- **Python 3.10+**
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## Quick Start

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

### Lobby (before game starts)
| Command | Who | Description |
|---------|-----|-------------|
| `/newgame` | Anyone | Create a new game in a group |
| `/join` | Anyone | Join the current game |
| `/leave` | Anyone | Leave before game starts |
| `/startgame` | GM | Start with preset role composition |
| `/startcustom` | GM | Start with custom role composition (via DM) |
| `/kick` | GM | Kick a player (inline buttons) |
| `/speed` | GM | Quick speed preset |
| `/timeoutconfig` | GM | Configure per-stage timeouts |
| `/mode` | GM | Toggle game modes |
| `/language` | GM | Set group language |

### During Game
| Command | Who | Description |
|---------|-----|-------------|
| `/myrole` | Player | Check your role (DM only) |
| `/history` | Anyone | View mission results |
| `/votehistory` | Anyone | View detailed vote history |
| `/abort` | GM | End the game immediately |

### Anytime
| Command | Who | Description |
|---------|-----|-------------|
| `/roles` | Anyone | Interactive role guide with descriptions |
| `/stats` | Anyone | Win/loss leaderboard for this group |
| `/start` | Anyone | Bot welcome / auto-show role if in game |

## Architecture

```
main.py                     # Entry point, handler registration
commands/
  game_admin.py             # /newgame, /startgame, /startcustom, variant selection
  game_playflow.py          # All game flow handlers, timeouts, modes, phases
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
  game_setting.py           # Config loader (switches on AVALON_DEBUG env var)
utils/
  language.py               # i18n message loading with fallback chain
  message_helper.py         # Player list formatting
languages/
  en/                       # English (message.toml, button.toml)
  zh-TW/                    # Traditional Chinese (message.toml, button.toml)
data/
  bot_data.pkl              # Persistent game state (auto-created, gitignored)
```

### Design Decisions

- **Callback-based flow** (not ConversationHandler) — supports cross-chat DM voting
- **Role registry in TOML** — metadata only; visibility logic in Python for flexibility
- **Game modes as Python classes** — `GameMode` base class with hooks (`modify_roles`, `on_game_start`, `on_mission_end`)
- **Per-group persistent language** — stored in `chat_data`, survives across games
- **PicklePersistence** — all game state persists across bot restarts

## Customization

### Adding a New Language

1. Copy `languages/en/` to `languages/{your_code}/`
2. Translate all keys in `message.toml` and `button.toml`
3. Add the language code to `languages` array in `conf/game_setting.toml`
4. Add a button for it in `commands/language.py`

### Adding a New Game Mode

1. Create a class in `game/game_modes.py` extending `GameMode`
2. Implement hooks: `modify_roles()`, `on_game_start()`, `on_mission_end()`
3. Register in `MODE_CLASSES` dict
4. Add display metadata to `conf/game_modes.toml`
5. Add `mode_name_{name}` to all `message.toml` files
6. Add phase handlers in `game_playflow.py` if the mode injects phases

### Adding New Roles

1. Add role metadata to `conf/roles.toml`
2. Add vision logic to `game/roles.py` `get_vision()` if the role has special sight
3. Add `role_name_X`, `role_desc_X`, `role_tip_X` to all `message.toml` files
4. Add role to variants in `conf/game_setting.toml` or use via `/startcustom`

### Modifying Game Rules

- Role compositions per player count: `conf/game_setting.toml`
- Mission sizes and fail requirements: per-variant in the TOML configs
- Default timeouts: `game/game_controller.py` `__init__`
- Speed presets: `SPEED_PRESETS` in `commands/game_playflow.py`

## Known Limitations

- Players must start a private chat with the bot before it can DM them (Telegram restriction)
- Only one game per group at a time
- Bot must be added to the group as a member
- PicklePersistence may need clearing (`rm data/bot_data.pkl`) after major updates that change class structure

## Contributing

This project is in early development. Issues, bug reports, and PRs are welcome at:
https://github.com/VTT99/Avalon-Telegram-bot

## License

Open source. Self-host, modify, and distribute freely.
