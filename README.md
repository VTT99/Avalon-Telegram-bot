# Avalon-Telegram-bot

A Telegram bot for playing **The Resistance: Avalon** in group chats.

## Setup

### 1. Create a virtual environment

```bash
python3 -m venv venv
```

### 2. Activate the virtual environment

**macOS / Linux:**
```bash
source venv/bin/activate
```

**Windows:**
```bash
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure the bot token

Create a `.env` file in the project root:

```
BOT_TOKEN=your_telegram_bot_token_here
```

You can get a bot token from [@BotFather](https://t.me/BotFather) on Telegram.

### 5. Run the bot

```bash
python main.py
```
