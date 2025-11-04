# Discord Bot + Flask Web App

## Overview
This is a Python application that combines a Discord bot (using discord.py) with a Flask web server. Both services run concurrently in the same application, allowing the Discord bot to handle commands while the Flask server provides a web interface and API endpoints.

## Recent Changes
- **2025-11-03**: Initial project setup
  - Installed discord.py, Flask, and requests dependencies
  - Created main.py with Discord bot and Flask server integration
  - Configured Discord connector integration for secure token management
  - Implemented basic bot commands: !ping, !info, !help
  - Added Flask routes: /, /health, /stats

## Project Architecture
- **main.py**: Main application file that runs both Discord bot and Flask server
- **Discord Bot**: Uses discord.py with command prefix `!`
- **Flask Server**: Runs on port 5000 with health check and stats endpoints
- **Authentication**: Uses Replit Discord connector for secure token management

## Discord Bot Commands
- `!ping` - Check bot latency
- `!info` - Show bot information (guilds, users, latency)
- `!help` - Display available commands

## Flask Endpoints
- `GET /` - Home endpoint with bot status and info
- `GET /health` - Health check endpoint
- `GET /stats` - Bot statistics (guilds, users, latency)

## Dependencies
- discord.py 2.6.4
- Flask 3.1.2
- requests 2.32.5

## Integration
- Discord connector (connection:conn_discord_01K95Z8VJBH8TDPYEC9JRT0JBK)

## Running the Application
The application runs both the Discord bot and Flask server concurrently. Flask runs in a background thread while the Discord bot runs in the main thread using asyncio.
