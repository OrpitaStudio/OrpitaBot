import discord
import json
import random 
import math # <-- [NEW] Import math for fees
from discord.ext import commands
from typing import Optional

# Import all our config and helper functions
from bot_config import (
    db, 
    get_wallet, 
    CURRENCIES, 
    CURRENCY_EMOJIS, 
    item_shop, 
    shop_items, 
    CURRENCY_VALUES
)

# This is a "Cog" - a class that holds a group of commands
class AllCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # [NEW] A set to store the message IDs of active cookie drops
        self.active_drops = set()

    # --- [NEW] Listener for Random Cookie Drops ---
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # 1. Ignore bots (including ourself)
        if message.author.bot:
            return

        # 2. Ignore commands (if message starts with prefix)
        # We need to get the prefix from the bot object
        if message.content.startswith(self.bot.command_prefix):
            return

        # 3. Define the random chance (e.g., 1 in 100)
        # You can change 100 to 50 to make it more common, or 200 for rarer
        chance = random.randint(1, 100)

        if chance == 1:
            try:
                # Send the drop message
                drop_msg = await message.channel.send("A wild cookie appeared! 🍪\nReact with 🍪 to claim it!")

                # Add the reaction for the user to click
                await drop_msg.add_reaction("🍪")

                # Add the message ID to our tracking list
                self.active_drops.add(drop_msg.id)
                print(f"Cookie dropped! Message ID: {drop_msg.id}")

            except discord.Forbidden:
                # This happens if the bot doesn't have permission to send/react
                print(f"Error: Bot missing permissions in channel {message.channel.id}")
            except Exception as e:
                print(f"Error during cookie drop: {e}")

    # --- [NEW] Listener for Reaction Claims ---
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.Member):
        # 1. Ignore bots (including ourself)
        if user.bot:
            return

        # 2. Check if the reaction is the correct emoji
        if str(reaction.emoji) != "🍪":
            return

        # 3. Check if the message is one of our active drops
        if reaction.message.id in self.active_drops:

            # --- This is a successful claim! ---

            # 1. Remove the drop from the active list (so it can't be claimed twice)
            try:
                self.active_drops.remove(reaction.message.id)
            except KeyError:
                return # Someone else claimed it in the same split-second

            # 2. Get the user's wallet and add the cookie
            user_id = str(user.id)
            wallet = get_wallet(user_id)
            wallet["cookie"] += 1
            db[user_id] = wallet # Save it back

            # 3. Edit the original message to show who won
            try:
                # We also clear reactions to make it clean
                await reaction.message.clear_reactions() 
                await reaction.message.edit(content=f"**{user.name}** claimed the cookie! 🍪")
            except discord.Forbidden:
                print("Could not edit drop message (missing permissions).")

            # 4. (Optional) Send a confirmation DM to the user
            try:
                await user.send("You successfully claimed 1 🍪 from a random drop!")
            except discord.Forbidden:
                print(f"Could not send DM to {user.name} (DMs disabled).")

            print(f"Cookie claimed by {user.name} (ID: {user_id})")

    # --- (Bot's Original Commands) ---
    @commands.command()
    async def ping(self, ctx):
        """Responds with the bot's latency"""
        # Note: Use self.bot inside cogs
        await ctx.send(f'🏓 Pong! Latency: {round(self.bot.latency * 1000)}ms')

    # --- [NEW] Gambling & Income Commands ---

    @commands.command()
    # Cooldown: 1 use per user every 24 hours (86400 seconds)
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def daily(self, ctx):
        """Claims your daily salary (1-5 cookies)."""
        user_id = str(ctx.author.id)
        wallet = get_wallet(user_id)

        # Get random reward (1-5 as requested)
        reward = random.randint(1, 5)

        wallet["cookie"] += reward
        db[user_id] = wallet # Save

        await ctx.send(f"You collected your daily salary of **{reward}** 🍪! Your new balance is `{wallet['cookie']}` cookies.")

    @commands.command()
    async def slots(self, ctx):
        """Spin the slot machine for 1 cookie!"""
        user_id = str(ctx.author.id)
        wallet = get_wallet(user_id)

        # --- Start Checks ---
        cost = 1 # Cost to play (as requested)
        if wallet.get("cookie", 0) < cost:
            await ctx.send(f"You need at least {cost} 🍪 to play the slots!")
            return

        # --- Take the cost ---
        wallet["cookie"] -= cost

        # --- Roll the slots ---
        # 5 emojis as requested
        emojis = ["🍒", "🍋", "💰", "💀", "🍪"]
        roll = [random.choice(emojis) for _ in range(3)]

        result_msg = f"You spin the slots... and get:\n\n**[ {roll[0]} | {roll[1]} | {roll[2]} ]**\n\n"

        # --- Check Winnings ---
        if roll[0] == roll[1] == roll[2]:
            # Three in a row (Jackpot!)
            if roll[0] == "💰":
                winnings = 100 # Jackpot
            else:
                winnings = 50 # Normal jackpot
            wallet["cookie"] += winnings
            result_msg += f"**JACKPOT!** You win `{winnings}` cookies! 🥳"

        elif roll[0] == roll[1] or roll[1] == roll[2] or roll[0] == roll[2]:
            # Two in a row
            winnings = 5
            wallet["cookie"] += winnings
            result_msg += f"You win `{winnings}` cookies! 🎉"

        else:
            # No win
            result_msg += "You lost. 😢 Better luck next time!"

        # Save wallet
        db[user_id] = wallet
        await ctx.send(result_msg)

    @commands.command()
    async def dice(self, ctx, amount: int):
        """Roll the dice for a 50/50 chance to double your cookie bet."""

        user_id = str(ctx.author.id)
        wallet = get_wallet(user_id)

        # --- Start Checks ---
        if amount <= 0:
            await ctx.send("You must bet at least 1 cookie.")
            return

        current_cookies = wallet.get("cookie", 0)

        if current_cookies < amount:
            await ctx.send(f"You don't have enough cookies! You only have `{current_cookies}` 🍪.")
            return
        # --- End Checks ---

        # 50/50 roll
        roll = random.choice(["win", "loss"])

        if roll == "win":
            # Add winnings
            wallet["cookie"] += amount
            db[user_id] = wallet # Save
            await ctx.send(f"🎲 You rolled... **WIN!**\nYou won `{amount}` cookies! 🍪 You now have `{wallet['cookie']}` cookies.")
        else:
            # Subtract losses
            wallet["cookie"] -= amount
            db[user_id] = wallet # Save
            await ctx.send(f"🎲 You rolled... **LOSE!**\nYou lost `{amount}` cookies. 😢 You now have `{wallet['cookie']}` cookies.")

    # --- [NEW] Give/Transfer Command ---
    @commands.command()
    async def give(self, ctx, member: discord.Member, amount: int):
        """Transfers your own cookies to another user."""

        item_name = "cookie" 
        giver_id = str(ctx.author.id)
        receiver_id = str(member.id)

        # --- Start Checks ---
        if giver_id == receiver_id:
            await ctx.send("You cannot give cookies to yourself.")
            return

        if amount <= 0:
            await ctx.send("You must give at least 1 cookie.")
            return

        giver_wallet = get_wallet(giver_id)
        current_cookies = giver_wallet.get(item_name, 0)

        if current_cookies < amount:
            await ctx.send(f"You don't have enough cookies! You only have `{current_cookies}` 🍪.")
            return
        # --- End Checks ---

        receiver_wallet = get_wallet(receiver_id)

        try:
            # Subtract from giver
            giver_wallet[item_name] -= amount
            # Add to receiver
            receiver_wallet[item_name] += amount

            # Save both wallets back to DB
            db[giver_id] = giver_wallet
            db[receiver_id] = receiver_wallet

            await ctx.send(f"✅ You gave {amount} 🍪 to {member.mention}!")

        except Exception as e:
            await ctx.send(f"An error occurred during the transfer: {e}")

    # --- [NEW] Steal Command ---
    @commands.command()
    @commands.cooldown(1, 3600, commands.BucketType.user) # 1 use per hour
    async def steal(self, ctx, member: discord.Member, amount: int):
        """Try to steal cookies from another user (30% success)."""

        stealer_id = str(ctx.author.id)
        victim_id = str(member.id)

        # --- Start Checks ---
        if stealer_id == victim_id:
            await ctx.send("You can't steal from yourself.")
            return

        if amount <= 0:
            await ctx.send("You must try to steal at least 1 cookie.")
            return

        stealer_wallet = get_wallet(stealer_id)
        victim_wallet = get_wallet(victim_id)

        # Check if stealer has enough to cover penalty (as requested)
        if stealer_wallet.get("cookie", 0) < amount:
            await ctx.send(f"You need at least `{amount}` 🍪 to attempt this (to cover the penalty if you fail).")
            return

        # Check if victim has enough to be stolen
        if victim_wallet.get("cookie", 0) < amount:
            await ctx.send(f"That user doesn't have `{amount}` 🍪 to steal.")
            return
        # --- End Checks ---

        # 30% success chance (as requested)
        success_chance = random.randint(1, 100)

        if success_chance <= 30:
            # --- SUCCESS ---
            stealer_wallet["cookie"] += amount
            victim_wallet["cookie"] -= amount

            db[stealer_id] = stealer_wallet
            db[victim_id] = victim_wallet

            await ctx.send(f"💰 **Success!** You stole `{amount}` 🍪 from {member.mention}!")

        else:
            # --- FAILURE ---
            stealer_wallet["cookie"] -= amount # Apply penalty
            db[stealer_id] = stealer_wallet

            await ctx.send(f"👮 **Failed!** You were caught trying to steal `{amount}` 🍪 from {member.mention}!\nYou paid a penalty of `{amount}` 🍪.")

    # --- [NEW] Bank Commands ---

    @commands.command()
    async def bank(self, ctx, member: Optional[discord.Member] = None):
        """Shows your bank balance (in hand vs. stored)."""
        if member is None:
            member = ctx.author

        wallet = get_wallet(str(member.id))

        embed = discord.Embed(
            title=f"🏦 {member.name}'s Bank Account",
            color=discord.Color.blue()
        )
        embed.add_field(name="In Hand ✋", value=f"`{wallet.get('cookie', 0)}` 🍪", inline=True)
        embed.add_field(name="In Bank 🏦", value=f"`{wallet.get('bank', 0)}` 🍪", inline=True)

        embed.set_footer(text="Bank deposits have a 3% fee. Stored money is taxed 3% every 24h.")
        await ctx.send(embed=embed)

    @commands.command()
    async def deposit(self, ctx, amount: int):
        """Deposits cookies into your bank (3% fee)."""
        user_id = str(ctx.author.id)
        wallet = get_wallet(user_id)

        # --- Checks ---
        if amount <= 0:
            await ctx.send("You must deposit at least 1 cookie.")
            return

        if wallet.get("cookie", 0) < amount:
            await ctx.send(f"You don't have enough cookies in hand. You only have `{wallet.get('cookie', 0)}` 🍪.")
            return

        # --- Calculate Fee (3% rounded up, min 1) ---
        # "مقربة لاقرب رقم صحيح لا يساوي الصفر"
        fee = max(1, math.ceil(amount * 0.03)) 
        amount_deposited = amount - fee

        if amount_deposited <= 0:
             await ctx.send(f"The deposit fee (`{fee}` 🍪) is more than the amount you are depositing!")
             return

        # --- Process Transaction ---
        wallet["cookie"] -= amount
        wallet["bank"] += amount_deposited
        db[user_id] = wallet

        await ctx.send(f"✅ Deposited `{amount_deposited}` 🍪 into your bank. (A fee of `{fee}` 🍪 was paid).")

    @commands.command()
    async def withdraw(self, ctx, amount: int):
        """Withdraws cookies from your bank (no fee)."""
        user_id = str(ctx.author.id)
        wallet = get_wallet(user_id)

        # --- Checks ---
        if amount <= 0:
            await ctx.send("You must withdraw at least 1 cookie.")
            return

        if wallet.get("bank", 0) < amount:
            await ctx.send(f"You don't have that much in your bank. You only have `{wallet.get('bank', 0)}` 🍪.")
            return

        # --- Process Transaction ---
        wallet["bank"] -= amount
        wallet["cookie"] += amount
        db[user_id] = wallet

        await ctx.send(f"✅ Withdrew `{amount}` 🍪 from your bank.")

    # --- [UPDATED] Cookie Reward Commands ---

    # 5. Award Currency Command (Admin Only) [!FIXED!]
    @commands.command()
    @commands.has_permissions(administrator=True) # <-- Makes this admin-only
    async def award(self, ctx, member: discord.Member, amount: int, item_name: str):
        """!award @username [amount] [item_name] - Adds to a user's balance."""
        user_id = str(member.id)
        item_name = item_name.lower()

        # Check if the item is valid
        if item_name not in CURRENCIES:
            await ctx.send(f"Error: '{item_name}' is not a valid item. Valid items are: {', '.join(CURRENCIES)}")
            return

        # Get or CREATE/FIX the wallet
        wallet = get_wallet(user_id) # Get/Create/Fix wallet (now a REAL dict)

        # Modify the REAL dict
        wallet[item_name] += amount

        # Save the REAL dict back to DB (this is now CRITICAL)
        db[user_id] = wallet 

        emoji = CURRENCY_EMOJIS.get(item_name, '🎁')
        await ctx.send(f"Awarded {amount} {emoji} to {member.mention}!")

    # 6. Balance Command (Wallet) [!MODIFIED!]
    @commands.command()
    # [FIX] Use Optional[] to tell the linter that None is allowed
    async def balance(self, ctx, member: Optional[discord.Member] = None):
        """!balance (shows your own balance) or !balance @username"""
        if member is None:
            member = ctx.author

        # Get or create/fix the user's wallet (now a REAL dict)
        # [FIX] Convert member.id (int) to str for the helper function
        wallet = get_wallet(str(member.id)) 

        embed = discord.Embed(
            title=f"💰 {member.name}'s Wallet",
            color=discord.Color.green()
        )

        # Calculate total net worth first
        total_worth = 0

        # Display all currencies in the wallet
        for item_name in CURRENCIES:
            # We don't count "bank" in this display loop
            if item_name == "bank" or item_name == "last_taxed": 
                continue
            amount = wallet.get(item_name, 0)
            embed.add_field(name=f"{CURRENCY_EMOJIS.get(item_name, '🎁')} {item_name.title()}", value=f"**{amount}**", inline=True)

            # Add to net worth
            total_worth += amount * CURRENCY_VALUES.get(item_name, 0)

        # Add bank balance separately to total worth
        bank_balance = wallet.get("bank", 0)
        total_worth += bank_balance * CURRENCY_VALUES.get("bank", 1)

        embed.description = f"**Total Net Worth:** `{total_worth}` 🍪"

        # Add Bank balance to the fields
        embed.add_field(name=f"{CURRENCY_EMOJIS.get('bank', '🏦')} Bank", value=f"**{bank_balance}**", inline=True)

        await ctx.send(embed=embed)

    # 7. Leaderboard Command [!FIXED!]
    @commands.command()
    async def leaderboard(self, ctx, count: int = 5):
        """!leaderboard (shows top 5 richest users)"""
        if count > 20: count = 20 # Max 20 users

        all_users = db.keys()
        leaderboard_data = {} # Will store {user_id: total_net_worth}

        for user_id in all_users:
            if user_id.isdigit(): # Check if it's a user ID

                # get_wallet() will now fix bad data,
                wallet = get_wallet(user_id) # Get user's wallet (or fix it)
                if not isinstance(wallet, dict):
                    continue 

                total_net_worth = 0

                # Calculate total net worth for this user
                for item_name, amount in wallet.items():
                    # We MUST include 'bank' in total net worth calculation
                    if item_name != "last_taxed":
                        item_value = CURRENCY_VALUES.get(item_name, 0) # Get value from our new map
                        total_net_worth += amount * item_value

                if total_net_worth > 0:
                    leaderboard_data[user_id] = total_net_worth

        # Sort them from highest to lowest
        sorted_users = sorted(leaderboard_data.items(), key=lambda item: item[1], reverse=True)

        embed = discord.Embed(title="🏆 Richest Users (by Net Worth)", color=discord.Color.gold())

        if not sorted_users:
            embed.description = "Nobody has any items yet!"
        else:
            embed.description = "The top users based on their total wallet value."

        for i, (user_id, net_worth) in enumerate(sorted_users[:count]):
            try:
                # Need to use self.bot to fetch user
                user = await self.bot.fetch_user(int(user_id))
                # Display the net worth in the value using Markdown
                embed.add_field(name=f"**{i+1}. {user.name}**", value=f"`{net_worth}` 🍪 Total Worth", inline=False)
            # [FIX] Changed bare 'except:' to 'except Exception:' to be safer
            except Exception: 
                embed.add_field(name=f"**{i+1}. Unknown User**", value=f"`{net_worth}` 🍪 Total Worth", inline=False)

        await ctx.send(embed=embed)

    # --- [UPDATED] Shop Commands ---

    # 8. Shop Command
    @commands.command()
    async def shop(self, ctx):
        """Displays all items and roles available for purchase"""
        embed = discord.Embed(title="🛒 Cookie Shop 🛒", description="Buy items or roles with your `cookie` currency!", color=discord.Color.dark_orange())

        # --- Item Shop Section ---
        item_list = []
        for key, details in item_shop.items():
            emoji = CURRENCY_EMOJIS.get(key, '🎁')
            # Using Markdown for better formatting
            item_list.append(f"**{details['name']} {emoji}**: `{details['price']}` 🍪\n*Type `!buy {key}` to purchase.*")

        if item_list:
            embed.add_field(
                name="--- ☕ Items ☕ ---",
                value="\n\n".join(item_list), # Added newlines for spacing
                inline=False
            )

        # --- Role Shop Section ---
        role_list = []
        for key, details in shop_items.items():
            # Using Markdown for better formatting
            role_list.append(f"**{details['name']}**: `{details['price']}` 🍪\n*Type `!buy {key}` to purchase.*")

        if role_list:
            embed.add_field(
                name="--- 👑 Roles 👑 ---",
                value="\n\n".join(role_list), # Added newlines for spacing
                inline=False
            )

        await ctx.send(embed=embed)

    # 9. Buy Command
    @commands.command()
    async def buy(self, ctx, *, item_key: str): # Use * to capture multi-word names if needed, though keys are single
        """!buy {item_name} - Buys an item or role from the shop"""
        item_key = item_key.lower().strip() # make it case-insensitive and remove spaces
        user_id = str(ctx.author.id)

        # Get the user's wallet (or create/fix it)
        wallet = get_wallet(user_id) # Now returns a REAL dict
        cookie_balance = wallet.get("cookie", 0)

        # --- Check Item Shop First ---
        if item_key in item_shop:
            item = item_shop[item_key]
            price = item["price"]

            # Check if user has enough cookies
            if cookie_balance < price:
                await ctx.send(f"You don't have enough cookies! You need `{price}` 🍪, but you only have `{cookie_balance}` 🍪.")
                return

            # Process the transaction
            try:
                # Take cookies
                wallet["cookie"] -= price
                # Give item
                if item_key not in wallet: wallet[item_key] = 0
                wallet[item_key] += 1
                # Save REAL dict back to DB
                db[user_id] = wallet

                emoji = CURRENCY_EMOJIS.get(item_key, '🎁')
                await ctx.send(f"Congratulations! You bought 1 **{item['name']}** {emoji} for `{price}` 🍪!")
            except Exception as e:
                await ctx.send(f"An unexpected error occurred: {e}")

        # --- Check Role Shop Second ---
        elif item_key in shop_items:
            item = shop_items[item_key]
            price = item["price"]
            role_id = item["role_id"]

            # Check if user has enough cookies
            if cookie_balance < price:
                await ctx.send(f"You don't have enough cookies! You need `{price}` 🍪, but you only have `{cookie_balance}` 🍪.")
                return

            # Check if user already has the role
            role = ctx.guild.get_role(role_id)
            if role is None:
                await ctx.send("Error: The role for this item is not set up correctly. Please contact an admin. (Invalid Role ID)")
                return

            if role in ctx.author.roles:
                await ctx.send("You already have this item/role!")
                return

            # Process the transaction
            try:
                # Take cookies
                wallet["cookie"] -= price
                # Save REAL dict back to DB
                db[user_id] = wallet
                # Give role
                await ctx.author.add_roles(role)
                await ctx.send(f"Congratulations! You bought the **{item['name']}** role for `{price}` 🍪!")

            except discord.Forbidden:
                await ctx.send("Error: I don't have permission to give you that role. (Check 'Manage Roles' permission & my role position).")
            except Exception as e:
                await ctx.send(f"An unexpected error occurred: {e}")
                # Give back cookies if something went wrong
                wallet["cookie"] += price
                db[user_id] = wallet

        # --- If Not Found ---
        else:
            await ctx.send("That item doesn't exist in the shop. Type `!shop` to see items.")

    # --- [NEW] Admin DB Management Commands ---

    @commands.command(name="admin_set")
    @commands.has_permissions(administrator=True)
    async def admin_set(self, ctx, member: discord.Member, amount: int, item_name: str):
        """(Admin) Sets a user's item count to a specific value."""
        user_id = str(member.id)
        item_name = item_name.lower()

        if item_name not in CURRENCIES:
            await ctx.send(f"Error: '{item_name}' is not a valid item. Valid items are: {', '.join(CURRENCIES)}")
            return

        wallet = get_wallet(user_id) # Get/Create/Fix wallet
        wallet[item_name] = amount # Set the value directly
        db[user_id] = wallet # Save

        await ctx.send(f"✅ Set {member.mention}'s **{item_name}** balance to **{amount}**.")

    @commands.command(name="reset_wallet")
    @commands.has_permissions(administrator=True)
    async def reset_wallet(self, ctx, member: discord.Member):
        """(Admin) Resets a single user's wallet to all zeros."""
        user_id = str(member.id)

        # Create a brand new, empty wallet
        new_wallet = {item: 0 for item in CURRENCIES}
        new_wallet["last_taxed"] = int(time.time()) # Also reset tax timer
        db[user_id] = new_wallet

        await ctx.send(f"✅ Reset {member.mention}'s wallet. All their items are now 0.")

    @commands.command(name="admin_dump")
    @commands.has_permissions(administrator=True)
    async def admin_dump(self, ctx):
        """(Admin) Shows the entire user database (if small enough)."""

        output_lines = ["--- Full User Database Dump ---"]
        all_keys = db.keys()
        user_count = 0

        for key in all_keys:
            if key.isdigit(): # Only process keys that are user IDs
                user_count += 1
                try:
                    # Need to use self.bot
                    user = await self.bot.fetch_user(int(key))
                    user_name = f"{user.name} ({key})"
                except Exception: # [FIX] Changed bare 'except:'
                    user_name = f"Unknown User ({key})"

                wallet_data = dict(db.get(key)) # Get the wallet (as a real dict)

                output_lines.append(f"\n--- {user_name} ---")
                output_lines.append(json.dumps(wallet_data, indent=2))

        if user_count == 0:
            await ctx.send("Database is empty. No user wallets found.")
            return

        full_output = "\n".join(output_lines)

        # Discord message limit is 2000 chars. We check 1900 to be safe.
        if len(full_output) > 1900:
            await ctx.send(f"Database dump is too large to display in Discord ({len(full_output)} characters).")
        else:
            await ctx.send(f"```json\n{full_output}\n```")


    @commands.command(name="wipe_db")
    @commands.has_permissions(administrator=True)
    async def wipe_db(self, ctx, confirmation: str = ""):
        """(Admin) Wipes all user wallets from the database."""
        if confirmation.lower() != "confirm":
            embed = discord.Embed(
                title="⚠️ DANGER: Database Wipe Confirmation",
                description="This command will **permanently delete** all user wallets (cookies, milk, etc.) from the database.",
                color=discord.Color.red()
            )
            embed.add_field(name="How to Confirm", value=f"To proceed, type:\n`!wipe_db confirm`")
            embed.set_footer(text="This action cannot be undone.")
            await ctx.send(embed=embed)
            return

        # If "confirm" was typed
        await ctx.send("Wiping database... -  wiping all user wallets.")
        deleted_count = 0
        all_keys = db.keys()

        for key in all_keys:
            if key.isdigit(): # This ensures we only delete user wallets (User IDs)
                del db[key]
                deleted_count += 1

        await ctx.send(f"✅ **Database Wipe Complete!**\nDeleted `{deleted_count}` user wallets.")
        await ctx.send("All users will start from `0` on their next `!balance` command.")

    # 10. New Help Command [!MODIFIED!]
    @commands.command()
    async def help(self, ctx):
        """Shows this help message"""
        embed = discord.Embed(
            title="Bot Help & Commands", # Emoji removed
            description="Here are all the commands, grouped by category.",
            color=discord.Color.blue()
        )

        # Economy Category
        econ_desc = (
            "`!balance [@User]` - Check your wallet (hand vs. bank).\n"
            "`!daily` - Claim your daily salary (1-5 cookies).\n"
            "`!dice [Amount]` - Bet cookies for a 50/50 win/loss.\n"
            "`!slots` - Spin the slot machine for 1 cookie.\n"
            "`!give @User [Amount]` - Give your cookies to another user.\n"
            "`!steal @User [Amount]` - Try to steal cookies (30% success).\n"
            "`!leaderboard [Count]` - Show the richest users (Default: 5).\n"
        )
        embed.add_field(name="Economy", value=econ_desc, inline=False) # Emoji removed

        # Bank Category
        bank_desc = (
            "`!bank [@User]` - Shows your hand vs. bank balance.\n"
            "`!deposit [Amount]` - Deposit cookies to your bank (3% fee).\n"
            "`!withdraw [Amount]` - Withdraw cookies from your bank.\n"
        )
        embed.add_field(name="Bank", value=bank_desc, inline=False)

        # Shop Category
        shop_desc = (
            "`!shop` - View all items and roles for sale.\n"
            "`!buy {item_name}` - Buy an item or role (e.g., `!buy milk`).\n"
        )
        embed.add_field(name="Shop", value=shop_desc, inline=False) # Emoji removed

        # Admin Category
        admin_desc = (
            "`!award @User [Amount] [Item]` - Give items to a user.\n"
            "*Example: `!award @User 5 cookie`*\n\n"
            "`!admin_set @User [Amount] [Item]` - Set a user's item count.\n"
            "*Example: `!admin_set @User 50 cookie`*\n\n"
            "`!reset_wallet @User` - Reset a user's wallet to all zeros.\n\n"
            "`!admin_dump` - **(ADVANCED)** Show the raw database data.\n\n"
            "`!wipe_db` - **(DANGER!)** Deletes all user wallets. Requires confirmation."
        )
        embed.add_field(name="Admin", value=admin_desc, inline=False) # Emoji removed

        # Other Category
        other_desc = (
            "`!ping` - Check if the bot is responsive.\n"
        )
        embed.add_field(name="Other", value=other_desc, inline=False) # Emoji removed

        embed.set_footer(text="All commands start with '!'")
        await ctx.send(embed=embed)


# This function is required to load the cog
async def setup(bot):
    await bot.add_cog(AllCommands(bot))