import os
import math # <-- [NEW] Import math for rounding up fees
import time # <-- [NEW] Import time for tax timestamps
from replit import db # Import the database
from typing import Optional

# --- [NEW] CURRENCY & SHOP CONFIGURATION ---

# Define all the currencies/items you want in your economy
# "cookie" is the main currency. "bank" is where money is stored.
CURRENCIES = ["cookie", "milk", "coffee", "matcha", "bank"]

# Assign an emoji for each item for display
CURRENCY_EMOJIS = {
    "cookie": "🍪",
    "milk": "🥛",
    "coffee": "☕",
    "matcha": "🍵",
    "bank": "🏦" # <-- [NEW]
}

# --- Item Shop (Buy items with Cookies) ---
# Users can buy these items. The price is in "cookie".
item_shop = {
    "milk": {
        "name": "Glass of Milk",
        "price": 10  # Price in cookies
    },
    "coffee": {
        "name": "Cup of Coffee",
        "price": 25
    },
    "matcha": {
        "name": "Matcha Latte",
        "price": 50
    }
}

# --- Role Shop (Buy roles with Cookies) ---
shop_items = {
    "bronze": {
        "name": "Bronze Role",
        "price": 100,
        "role_id": 123456789012345678  # <-- EDIT THIS
    },
    "silver": {
        "name": "Silver Role",
        "price": 500,
        "role_id": 123456789012345678  # <-- EDIT THIS
    },
    "gold": {
        "name": "Gold Role",
        "price": 1000,
        "role_id": 123456789012345678  # <-- EDIT THIS
    }
}

# --- [NEW] Currency Value Mapping ---
# Automatically creates a value map for all currencies based on their price in cookies
# This is used to calculate total net worth for the leaderboard
CURRENCY_VALUES = {
    "cookie": 1,  # The base currency is worth 1
    "bank": 1     # Money in the bank is worth 1
}
# Add all items from the item_shop to the value map
for key, details in item_shop.items():
    if key in CURRENCIES:
        CURRENCY_VALUES[key] = details["price"]

# ---------------------------------

# 3. Helper Function: Get/Create User Wallet [!HEAVILY MODIFIED FOR BANK TAX!]
def get_wallet(user_id: str):
    """
    Safely gets a user's wallet.
    Applies 24-hour bank tax if necessary.
    If the user is new OR their data is in an old/bad format,
    it creates a new, default wallet for them.
    """
    user_id = str(user_id)
    current_time = int(time.time())

    try:
        # Try to get the wallet
        wallet_proxy = db.get(user_id)

        # --- [THE FIX] ---
        # Convert the "Proxy Object" (ObservedDict) from replit-db
        # into a REAL dictionary. This prevents silent save failures.
        wallet = dict(wallet_proxy)
        # --- [END FIX] ---

        # Check if it's a valid wallet (a dictionary)
        if not isinstance(wallet, dict):
            raise TypeError("Old data format found. Overwriting.")

        # Check if the wallet is missing any new currencies
        is_updated = False
        for item in CURRENCIES:
            if item not in wallet:
                wallet[item] = 0
                is_updated = True

        # --- [NEW] Bank Tax Logic (Lazy Evaluation) ---
        if "last_taxed" not in wallet:
                wallet["last_taxed"] = current_time
                is_updated = True

        time_since_tax = current_time - wallet["last_taxed"]

        # Has it been 24 hours (86400 seconds)?
        if time_since_tax > 86400:
            bank_balance = wallet.get("bank", 0)
            if bank_balance > 0:
                # Calculate how many 24h periods have passed
                days_passed = time_since_tax // 86400

                # Apply 3% tax for each day passed
                # (0.97 ** days_passed) = (1 - 0.03) ^ days
                taxed_balance = bank_balance * (0.97 ** days_passed)
                wallet["bank"] = int(taxed_balance) # Store as integer

                print(f"Taxed user {user_id} for {days_passed} day(s).")

            # Update the last taxed time
            wallet["last_taxed"] = current_time
            is_updated = True
        # --- [END NEW] ---

        if is_updated:
            db[user_id] = wallet # Save updates

        return wallet

    except (TypeError, KeyError, AttributeError, ValueError):
        # Create and return a new, default (empty) wallet.
        new_wallet = {item: 0 for item in CURRENCIES}
        new_wallet["last_taxed"] = current_time # <-- [NEW] Set tax time
        db[user_id] = new_wallet
        return new_wallet