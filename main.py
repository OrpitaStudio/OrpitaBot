import discord
import os
import asyncio 
from discord.ext import commands
from flask import Flask, jsonify
from threading import Thread
from typing import Optional
import math # <-- [NEW] Import math for cooldown timer

# --- (Keep Alive Section (from AI code)) ---
# This will keep the bot running 24/7 with UptimeRobot
app = Flask('')

@app.route('/')
def home():
    # This is the route UptimeRobot will visit
    return jsonify({'status': 'Bot is alive!'})

def run_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    # This function runs the web server in a separate thread
    t = Thread(target=run_server)
    t.start()
# ----------------------------------------------------

# --- (Bot Section) ---

# 1. Define Intents
intents = discord.Intents.default()
intents.message_content = True # To read messages
intents.members = True         # To see member information
intents.guilds = True          # Required for role management

# 2. Define the Bot (Prefix is !)
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# 3. On Ready Event (Simple)
@bot.event
async def on_ready():
    print(f'Bot logged in as: {bot.user}')
    print('---------------------------')

# 4. (Important) Error Handling (Moved from main file)
@bot.event
async def on_command_error(ctx, error):
    # --- [NEW] Cooldown Error Handling ---
    if isinstance(error, commands.CommandOnCooldown):
        # Format the remaining time
        seconds_remaining = int(error.retry_after)
        hours, remainder = divmod(seconds_remaining, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            time_left = f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            time_left = f"{minutes}m {seconds}s"
        else:
            time_left = f"{seconds}s"

        await ctx.send(f"This command is on cooldown. Please try again in **{time_left}**.")
    # --- [END NEW] ---

    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You do not have permission to use this command. 👮‍♂️")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send(f"Error: Could not find that member. Please check the mention and try again.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Error: You forgot an argument. Usage: `{ctx.prefix}{ctx.command.name} {ctx.command.signature}`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"Error: Invalid argument. Make sure you are using the command correctly.")
    else:
        # Print other errors to the console for debugging
        print(f"An unexpected error occurred: {error}") 

# --- [NEW] Main async function to load Cogs and run the bot ---
async def main():
    # Get the token
    token = os.environ.get('DISCORD_BOT_TOKEN') 
    if not token:
        print("[Error] Bot token not found in Secrets (🔒)")
        return

    # Start the keep-alive server
    keep_alive() 

    # Load the commands from our other file
    try:
        await bot.load_extension('bot_commands')
        print("Successfully loaded 'bot_commands.py'")
    except Exception as e:
        print(f"Failed to load 'bot_commands.py': {e}")

    # Start the bot
    try:
        await bot.start(token)
    except Exception as e:
        print(f"[Error] An issue occurred: {e}")

# --- (Run Section) ---
if __name__ == "__main__":
    asyncio.run(main())