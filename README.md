# Discord Bot + Flask Web App

A Python application that combines a Discord bot (using discord.py) with a Flask web server. Both services run concurrently, allowing the Discord bot to handle commands while the Flask server provides a web interface and API endpoints.

## Features

### Discord Bot
- **Command Prefix**: `!`
- **Available Commands**:
  - `!ping` - Check bot latency
  - `!info` - Show bot information (guilds, users, latency)
  - `!help` - Display available commands

### Flask Web Server
- **Port**: 5000
- **Endpoints**:
  - `GET /` - Home endpoint with bot status and info
  - `GET /health` - Health check endpoint
  - `GET /stats` - Bot statistics (guilds, users, latency)

## Setup Instructions

### 1. Create a Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" section in the left sidebar
4. Click "Add Bot" or "Reset Token"
5. Copy the bot token (you'll need this for the next step)

### 2. Enable Required Intents (IMPORTANT!)

In the Discord Developer Portal, under the "Bot" section, enable these Privileged Gateway Intents:
- ✅ **Message Content Intent** (REQUIRED - bot won't start without this!)

**This step is mandatory!** Without enabling Message Content Intent, the bot will fail to connect with a `PrivilegedIntentsRequired` error.

### 3. Add the Bot to Your Server

1. In the Discord Developer Portal, go to "OAuth2" > "URL Generator"
2. Select scopes:
   - `bot`
3. Select bot permissions:
   - Send Messages
   - Read Message History
   - Embed Links
   - Add Reactions
4. Copy the generated URL and open it in your browser
5. Select the server where you want to add the bot

### 4. Configure the Bot Token

The bot token should already be set in your Replit Secrets as `DISCORD_BOT_TOKEN`.

## Running the Application

The application automatically starts both the Discord bot and Flask server when you run `main.py`. You can see the status in the console output.

## Project Structure

```
.
├── main.py           # Main application file
├── README.md         # This file
├── replit.md         # Project documentation
├── .gitignore        # Git ignore rules
├── pyproject.toml    # Python project configuration
└── uv.lock           # Dependency lock file
```

## Dependencies

- discord.py 2.6.4 - Discord bot library
- Flask 3.1.2 - Web framework
- aiohttp - Async HTTP client (required by discord.py)

## Troubleshooting

### Bot won't connect
- Make sure you've enabled the required intents in the Discord Developer Portal
- Verify your bot token is correct
- Check that the bot has been invited to at least one server

### Flask server won't start
- Ensure port 5000 is not being used by another process
- Check the console logs for specific error messages

### Commands not working
- Make sure "Message Content Intent" is enabled in the Discord Developer Portal
- Verify the bot has the necessary permissions in your server
- Commands must be prefixed with `!`

## Architecture

The application uses threading to run Flask and asyncio to run the Discord bot:
- Flask runs in a background daemon thread
- Discord bot runs in the main thread using asyncio
- Both services share the same Python process

This allows the web server to display real-time information about the bot's status while the bot handles Discord commands.
