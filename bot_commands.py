import discord
import json
import random 
import math 
import time # [تم التصحيح] استيراد time
from discord.ext import commands, tasks # [تم التصحيح] استيراد tasks
from typing import Optional
from replit import db # [تم التصحيح] استيراد db مباشرة

# Import all our config and helper functions
from bot_config import (
    get_wallet, 
    CURRENCIES, 
    CURRENCY_EMOJIS, 
    item_shop, 
    shop_items, 
    CURRENCY_VALUES,
    TEMPORARY_ITEMS
)

TAX_INTERVAL_SECONDS = 86400 # 24 hours

# This is a "Cog" - a class that holds a group of commands
class AllCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_drops = set()
        self.admin_drops = {}

        self.tax_loop.start()
        self.temp_nick_task.start()

    # [تم التصحيح] cog_unload أصبحت async
    async def cog_unload(self):
        self.tax_loop.cancel()
        self.temp_nick_task.cancel()
        print("Tax and Nickname loops cancelled.")


    @commands.Cog.listener()
    async def on_ready(self):
        print("Tax and Nickname loops initialized in background.")

    # --- [NEW] Automatic Tax Loop (Runs every 24 hours) ---
    @tasks.loop(seconds=TAX_INTERVAL_SECONDS) # 86400 seconds = 24 hours
    async def tax_loop(self):
        print("Starting bank tax calculation for all users...")
        current_time = int(time.time())
        taxed_users_count = 0

        # Iterate over all user IDs in the database
        all_user_ids = list(db.keys())

        for user_id in all_user_ids:
            # Only process keys that look like user IDs (digits)
            if user_id.isdigit():
                try:
                    # Get wallet (it only ensures structure now, not taxing)
                    wallet = get_wallet(user_id) 

                    # Check if enough time has passed since last tax
                    last_taxed = wallet.get("last_taxed", 0)
                    time_since_tax = current_time - last_taxed

                    if time_since_tax >= TAX_INTERVAL_SECONDS:
                        bank_balance = wallet.get("bank", 0)
                        days_passed = time_since_tax // TAX_INTERVAL_SECONDS

                        if bank_balance > 0:
                            # Apply 3% tax for each day passed (compounding)
                            # (0.97 ** days_passed) = (1 - 0.03) ^ days
                            taxed_balance = bank_balance * (0.97 ** days_passed)

                            # Calculate loss for logging (optional, but recommended)
                            loss = bank_balance - int(taxed_balance) 

                            wallet["bank"] = int(taxed_balance) # Store as integer
                            print(f"Taxed user {user_id} for {days_passed} day(s). Loss: {loss}")
                            taxed_users_count += 1

                        # Update the last taxed time to the end of the last full period
                        wallet["last_taxed"] = last_taxed + (days_passed * TAX_INTERVAL_SECONDS)

                        # Save the updated wallet back to DB
                        db[user_id] = wallet

                except Exception as e:
                    print(f"Error processing tax for user {user_id}: {e}")

        print(f"Finished taxing. Total users taxed: {taxed_users_count}")

    # --- [NEW] Background task for temporary nickname reversion ---
    @tasks.loop(minutes=5) # Check every 5 minutes
    async def temp_nick_task(self):
        print("Starting temporary nickname check...")
        current_time = int(time.time())

        # Iterate over ALL database keys (looking for users)
        for user_id in list(db.keys()):
            if user_id.isdigit():
                try:
                    wallet = get_wallet(user_id)

                    # Check for expiration data
                    expires = wallet.get('nick_expires', 0)
                    emoji = wallet.get('nick_emoji', None)

                    if emoji and expires > 0 and current_time >= expires:
                        # Nickname has expired, revert it!

                        member = None
                        # We must iterate all guilds to find the member
                        for guild in self.bot.guilds:
                            member = guild.get_member(int(user_id))
                            if member:
                                break

                        if member:
                            current_nick = member.nick if member.nick else member.name

                            # Check if the expected temporary emoji is still the prefix
                            expected_prefix = emoji

                            if current_nick and current_nick.startswith(expected_prefix): 
                                new_nick = current_nick.lstrip(expected_prefix).lstrip() 

                                # Find the permanent role emoji if present to prepend it back
                                permanent_prefix = self._get_permanent_emoji_prefix(member)
                                new_nick = permanent_prefix + new_nick

                                try:
                                    # Discord requires non-empty string for nick change
                                    await member.edit(nick=new_nick if new_nick else None) 
                                    print(f"Reverted temporary nickname for {member.name}.")
                                except discord.Forbidden:
                                    print(f"Forbidden: Could not revert nick for {member.name}.")
                                except Exception as e:
                                    print(f"Error reverting nick for {member.name}: {e}")

                        # 2. Clear the expiration data from DB regardless
                        wallet.pop('nick_expires', None)
                        wallet.pop('nick_emoji', None)
                        db[user_id] = wallet

                except Exception as e:
                    print(f"Error in nick revert loop for {user_id}: {e}")

    # [جديد] Helper method to get the permanent emoji prefix
    def _get_permanent_emoji_prefix(self, member: discord.Member) -> str:

        # Check Gold, Silver, Bronze roles in order for simplicity
        # NOTE: Using int() on role_id ensures compatibility if stored as str
        if member.get_role(int(shop_items['gold']['role_id'])):
             return shop_items['gold']['emoji'] + " "
        if member.get_role(int(shop_items['silver']['role_id'])):
             return shop_items['silver']['emoji'] + " "
        if member.get_role(int(shop_items['bronze']['role_id'])):
             return shop_items['bronze']['emoji'] + " "

        return ""

    # [جديد] Helper method to apply Nickname
    async def _apply_nickname_prefix(self, member: discord.Member, emoji: str, is_permanent: bool = False):
        current_nick = member.nick if member.nick else member.name

        # 1. Strip ALL existing known prefixes (temp and perm)
        cleaned_nick = current_nick

        # Remove permanent prefix if found
        for key, details in shop_items.items():
            perm_emoji = details.get('emoji', '')
            if perm_emoji and cleaned_nick.startswith(perm_emoji):
                cleaned_nick = cleaned_nick.lstrip(perm_emoji).lstrip()
                break # Assume only one permanent prefix is active

        # Remove temporary prefix if found
        for item_key, item_details in TEMPORARY_ITEMS.items():
            temp_emoji = item_details['emoji']
            # We must use 'temp_emoji + " "' as the prefix structure
            if cleaned_nick.startswith(temp_emoji + " "):
                cleaned_nick = cleaned_nick.lstrip(temp_emoji + " ").lstrip()
                break # Assume only one temporary prefix is active

        # 2. Re-apply prefixes

        # If the cleaned_nick is empty (i.e., nickname was just emojis), use the member's original name
        if not cleaned_nick or cleaned_nick.isspace(): 
            cleaned_nick = member.name

        perm_prefix = ""
        # Re-get permanent prefix by checking roles again (safer if roles changed)
        for key, details in shop_items.items():
             role_id = int(details['role_id']) 
             role = member.guild.get_role(role_id)
             if role and role in member.roles:
                 perm_prefix = details.get('emoji', '') + " "
                 break

        if is_permanent:
            # If buying a role (permanent), apply the new permanent emoji after cleaning
            final_nick = emoji + " " + cleaned_nick
        else:
            # If using an item (temporary), temporary goes first
            temp_prefix = emoji + " "
            final_nick = temp_prefix + perm_prefix + cleaned_nick

        try:
            # Ensure the final nick doesn't exceed Discord's max length (32 chars)
            if len(final_nick) > 32:
                 final_nick = final_nick[:32]

            # [تصحيح] إذا كان الاسم المستعار هو نفسه اسم المستخدم، اتركه None (لإزالته)
            if final_nick.strip() == member.name: 
                await member.edit(nick=None)
            else:
                await member.edit(nick=final_nick)
            return True
        except discord.Forbidden:
            return False
        except Exception as e:
            print(f"Error applying nickname for {member.name}: {e}")
            return False

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

    # --- [NEW] Listener for Reaction Claims (Modified to handle Admin Drop) ---
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.Member):
        # 1. Ignore bots (including ourself)
        if user.bot:
            return

        # 2. Check if the reaction is the correct emoji
        if str(reaction.emoji) != "🍪":
            return

        message_id = reaction.message.id
        claimed_amount = 0

        # --- Check for Regular Drop (1 Cookie) ---
        if message_id in self.active_drops:
            claimed_amount = 1
            # 1. Remove the drop from the active list
            try:
                self.active_drops.remove(message_id)
            except KeyError:
                return # Someone else claimed it

        # --- Check for Admin Drop (Variable Cookies) ---
        elif message_id in self.admin_drops:
            # Use .pop() to get the amount and remove the ID in one atomic operation.
            try:
                claimed_amount = self.admin_drops.pop(message_id)
            except KeyError:
                return # Someone else claimed it

        if claimed_amount > 0:
            # --- This is a successful claim! ---
            user_id = str(user.id)
            wallet = get_wallet(user_id)
            wallet["cookie"] += claimed_amount
            db[user_id] = wallet # Save it back

            # 3. Edit the original message to show who won
            try:
                await reaction.message.clear_reactions() 
                await reaction.message.edit(content=f"**{user.name}** claimed **{claimed_amount}** 🍪!")
            except discord.Forbidden:
                print("Could not edit drop message (missing permissions).")

            # 4. (Optional) Send a confirmation DM to the user
            try:
                await user.send(f"You successfully claimed **{claimed_amount}** 🍪 from a drop!")
            except discord.Forbidden:
                print(f"Could not send DM to {user.name} (DMs disabled).")

            print(f"Cookie claimed by {user.name} (ID: {user_id}), Amount: {claimed_amount}")
            return # Exit the function

        # If we reach here, it was neither an active drop nor an admin drop.
        return 

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
        # 6 emojis as requested
        emojis = ["🥔", "🥛", "☕", "🍵", "🍪", "💰"]
        roll = [random.choice(emojis) for _ in range(3)]

        result_msg = f"You spin the slots... and get:\n\n**[ {roll[0]} | {roll[1]} | {roll[2]} ]**\n\n"

        # --- Check Winnings ---
        if roll[0] == roll[1] == roll[2]:
            # Three in a row (Jackpot!)
            if roll[0] == "💰":
                winnings = 100 # Mega Jackpot
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

    # --- [NEW] Item Use Commands (Added) ---

    @commands.command()
    async def use(self, ctx, item_key: str):
        """!use {item_name} - Uses 5 items to get a temporary emoji next to your name for 24h."""
        item_key = item_key.lower().strip()
        user_id = str(ctx.author.id)

        if item_key not in TEMPORARY_ITEMS:
            await ctx.send("That item is not usable for a temporary nickname.")
            return

        item_details = TEMPORARY_ITEMS[item_key]
        cost = item_details['cost']
        emoji = item_details['emoji']

        wallet = get_wallet(user_id)
        current_items = wallet.get(item_key, 0)

        if current_items < cost:
            item_emoji = CURRENCY_EMOJIS.get(item_key, '🎁')
            await ctx.send(f"You need `{cost}` {item_emoji} {item_key.title()} to use this effect, but you only have `{current_items}`.")
            return

        # --- Process Use ---

        # 1. Deduct items
        wallet[item_key] -= cost

        # 2. Calculate Expiry
        expiry_time = int(time.time()) + (24 * 3600) # 24 hours in seconds

        # 3. Apply Nickname Change and Save Data
        if await self._apply_nickname_prefix(ctx.author, emoji, is_permanent=False):
            wallet['nick_emoji'] = emoji
            wallet['nick_expires'] = expiry_time
            db[user_id] = wallet

            await ctx.send(f"✅ Used `{cost}` {item_details['emoji']} {item_key.title()}. Your name now has the {emoji} emoji for 24 hours!")
        else:
            # Revert deduction if nickname change fails
            wallet[item_key] += cost
            db[user_id] = wallet
            await ctx.send("⚠️ Failed to change your nickname. Please check my role permissions and position, or that your nickname isn't too long.")

    @commands.command(name="check_status", aliases=['status'])
    async def check_status(self, ctx):
        """Checks how long until your temporary item emoji expires."""
        user_id = str(ctx.author.id)
        wallet = get_wallet(user_id)

        expires = wallet.get('nick_expires', 0)
        emoji = wallet.get('nick_emoji', None)
        current_time = int(time.time())

        if not emoji or expires <= current_time:
            await ctx.send("You do not currently have an active temporary item effect.")
            return

        time_left_seconds = expires - current_time

        hours, remainder = divmod(time_left_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            time_left_str = f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            time_left_str = f"{minutes}m {seconds}s"
        else:
            time_left_str = f"{seconds}s"

        await ctx.send(f"Your temporary effect ({emoji}) expires in: **{time_left_str}**.")


    # --- [UPDATED] Shop Commands ---

    @commands.command()
    async def shop(self, ctx):
        """Displays all items and roles available for purchase"""
        embed = discord.Embed(title="🛒 Cookie Shop 🛒", description="Buy items or roles with your `cookie` currency!", color=discord.Color.dark_orange())

        # --- Item Shop Section ---
        item_list = []
        for key, details in item_shop.items():
            emoji = CURRENCY_EMOJIS.get(key, '🎁')
            # Using Markdown for better formatting
            item_list.append(f"**{details['name']} {emoji}**: `{details['price']}` 🍪\n*Type `!buy {key}` to purchase or `!sell {key} [amount]` to sell.*")

        if item_list:
            embed.add_field(
                name="--- ☕ Items ☕ ---",
                value="\n\n".join(item_list), # Added newlines for spacing
                inline=False
            )

        # --- Role Shop Section ---
        role_list = []
        for key, details in shop_items.items():
            price_currency = details.get("currency", "cookie")
            price_emoji = CURRENCY_EMOJIS.get(price_currency, '🎁')

            # [تم التعديل] عرض العملة المطلوبة
            role_list.append(f"**{details['name']} ({details.get('emoji', '')})**: `{details['price']}` {price_emoji} ({price_currency.title()})\n*Type `!buy {key}` to purchase.*")

        if role_list:
            embed.add_field(
                name="--- 👑 Roles 👑 ---",
                value="\n\n".join(role_list), # Added newlines for spacing
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.command()
    async def buy(self, ctx, *, item_key: str):
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
            perm_emoji = item.get("emoji", "") # [تم الحصول على الرمز الدائم]

            # [تم التعديل] يتم الحصول على العملة المطلوبة
            required_currency = item.get("currency", "cookie") 
            required_balance = wallet.get(required_currency, 0)
            required_emoji = CURRENCY_EMOJIS.get(required_currency, '🎁')

            # Check if user has enough of the required currency
            if required_balance < price: 
                await ctx.send(f"You don't have enough {required_currency}! You need `{price}` {required_emoji}, but you only have `{required_balance}` {required_emoji}.")
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
                # Take the required currency
                wallet[required_currency] -= price
                # Save REAL dict back to DB
                db[user_id] = wallet
                # Give role
                await ctx.author.add_roles(role)

                # [جديد] تطبيق الرمز الدائم
                if perm_emoji:
                    # نمرر الرمز والـ flag True
                    await self._apply_nickname_prefix(ctx.author, perm_emoji, is_permanent=True)

                await ctx.send(f"Congratulations! You bought the **{item['name']}** role for `{price}` {required_emoji}!")

            except discord.Forbidden:
                await ctx.send("Error: I don't have permission to give you that role. (Check 'Manage Roles' permission & my role position).")
            except Exception as e:
                await ctx.send(f"An unexpected error occurred: {e}")
                # Give back currency if something went wrong
                wallet[required_currency] += price
                db[user_id] = wallet

        # --- If Not Found ---
        else:
            await ctx.send("That item doesn't exist in the shop. Type `!shop` to see items.")

    # --- [NEW] Admin Drop Command (Added) ---
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def admin_drop(self, ctx, amount: int):
        """(Admin) Drops a specific amount of cookies for users to claim."""
        if amount <= 0:
            await ctx.send("The drop amount must be at least 1 cookie.")
            return

        try:
            # Send the drop message
            drop_msg = await ctx.send(f"An admin dropped **{amount}** 🍪! The first to react with 🍪 claims it!")

            # Add the reaction for the user to click
            await drop_msg.add_reaction("🍪")

            # Add the message ID and amount to our tracking dictionary
            self.admin_drops[drop_msg.id] = amount
            print(f"Admin drop created! Message ID: {drop_msg.id}, Amount: {amount}")

        except discord.Forbidden:
            await ctx.send("Error: Bot missing permissions to send or react.")
        except Exception as e:
            print(f"Error during admin cookie drop: {e}")
            await ctx.send("An unexpected error occurred while creating the drop.")


    # --- [NEW] Sell Command (Added in previous step) ---
    @commands.command()
    async def sell(self, ctx, item_key: str, amount: int):
        """!sell {item_name} [amount] - Sells items for cookies (10% tax)."""
        item_key = item_key.lower().strip()
        user_id = str(ctx.author.id)

        # --- Initial Checks ---
        if item_key not in item_shop:
            await ctx.send("That item cannot be sold or doesn't exist. Check `!shop` for sellable items.")
            return

        if amount <= 0:
            await ctx.send("You must sell at least 1 item.")
            return

        wallet = get_wallet(user_id)

        # Check user's item balance
        current_items = wallet.get(item_key, 0)
        if current_items < amount:
            await ctx.send(f"You only have `{current_items}` {item_key.title()} to sell.")
            return

        # --- Calculation ---

        # Get the original purchase price (which is the sell value per unit in cookies)
        unit_sell_price = item_shop[item_key]["price"]

        # Total cookies received before tax
        total_received_cookies = amount * unit_sell_price

        # Calculate Tax (10% rounded up, min 1, greater than zero)
        # The fee logic is: max(1, math.ceil(amount * tax_rate))
        tax_rate = 0.10
        fee = max(1, math.ceil(total_received_cookies * tax_rate))

        net_gain = total_received_cookies - fee

        # Check if the fee consumes all the money
        if net_gain <= 0:
            await ctx.send(
                f"Selling `{amount}` {item_key.title()} is worth only `{total_received_cookies}` 🍪.\n"
                f"The minimum tax of `{fee}` 🍪 consumes all the value. Sale cancelled."
            )
            return

        # --- Transaction ---

        # 1. Deduct items
        wallet[item_key] -= amount

        # 2. Add cookies (the "cookie" key is guaranteed to exist by get_wallet)
        wallet["cookie"] += int(net_gain) # Add the net gain

        # 3. Save
        db[user_id] = wallet

        item_emoji = CURRENCY_EMOJIS.get(item_key, '🎁')

        await ctx.send(
            f"✅ You sold `{amount}` **{item_key.title()}** {item_emoji}.\n"
            f"Value: `{total_received_cookies}` 🍪. Tax (10%): `{fee}` 🍪.\n"
            f"You received a net gain of **`{int(net_gain)}`** 🍪."
        )


    # 5. Award Currency Command (Admin Only) [!FIXED!]
    @commands.command()
    @commands.has_permissions(administrator=True) # <-- Makes this admin-only
    async def award(self, ctx, member: discord.Member, amount: int, item_name: str):
        """!award @username [amount] [item_name] - Adds to a user's balance."""
        user_id = str(member.id)
        item_name = item_name.lower()

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
            except Exception: 
                embed.add_field(name=f"**{i+1}. Unknown User**", value=f"`{net_worth}` 🍪 Total Worth", inline=False)

        await ctx.send(embed=embed)


# This function is required to load the cog
async def setup(bot):
    await bot.add_cog(AllCommands(bot))
