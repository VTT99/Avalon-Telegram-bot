# Avalon-Telegram-bot

A Telegram bot for playing **The Resistance: Avalon** in group chats.

## Requirements

- **Python 3.10+** (uses modern type hints like `int | None`, `dict[str, ...]`)

## Setup

### 1. Install Python 3.10+

**macOS (Homebrew):**
```bash
brew install python@3.12
```

**Ubuntu / Debian:**
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv
```

**Windows:**

Download from https://www.python.org/downloads/ (3.10 or newer).

### 2. Create a virtual environment

```bash
python3 -m venv venv
```

### 3. Activate the virtual environment

**macOS / Linux:**
```bash
source venv/bin/activate
```

**Windows:**
```bash
venv\Scripts\activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure the bot token

Create a `.env` file in the project root:

```
BOT_TOKEN=your_telegram_bot_token_here
```

You can get a bot token from [@BotFather](https://t.me/BotFather) on Telegram.

### 6. Run the bot

```bash
python main.py             # Normal mode (5-10 players)
python main.py --debug     # Debug mode (2-10 players, for testing)
```
