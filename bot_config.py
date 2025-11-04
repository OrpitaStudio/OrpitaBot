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

# --- Role Shop (Buy roles with special items) ---
# [تم التعديل] price يمثل الآن الكمية المطلوبة من العملة المحددة في "currency"
shop_items = {
    "bronze": {
        "name": "Bronze Role",
        "price": 10,       # يتطلب 10 وحدات من العملة الجديدة
        "currency": "milk",  # [تم التحديد] يُشترى باللبن
        "role_id": 123456789012345678, 
        "emoji": "🥉" # [جديد] رمز دائم للرتبة
    },
    "silver": {
        "name": "Silver Role",
        "price": 20,       # يتطلب 20 وحدة من العملة الجديدة
        "currency": "coffee", # [تم التحديد] يُشترى بالقهوة
        "role_id": 123456789012345678, 
        "emoji": "🥈" # [جديد] رمز دائم للرتبة
    },
    "gold": {
        "name": "Gold Role",
        "price": 20,       # يتطلب 20 وحدة من العملة الجديدة
        "currency": "matcha", # [تم التحديد] يُشترى بالماتشا
        "role_id": 123456789012345678, 
        "emoji": "🥇" # [جديد] رمز دائم للرتبة
    }
}

# --- [NEW] Item Usage Configuration ---
# العناصر التي يمكن استخدامها لتغيير Nickname مؤقتاً
TEMPORARY_ITEMS = {
    "milk": {
        "cost": 5,
        "emoji": "🥛" 
    },
    "coffee": {
        "cost": 5,
        "emoji": "☕" 
    },
    "matcha": {
        "cost": 5,
        "emoji": "🍵" 
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

# 3. Helper Function: Get/Create User Wallet [!MODIFIED - تم نقل منطق الضريبة!]
def get_wallet(user_id: str):
    """
    Safely gets a user's wallet. 
    (NOTE: Tax application logic MOVED to a background loop in bot_commands.py)
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

        # --- [TAX TIME SETUP REMAINS] ---
        # Ensure the 'last_taxed' key exists for new/old users
        if "last_taxed" not in wallet:
                wallet["last_taxed"] = current_time
                is_updated = True
        # --- [TAX APPLICATION REMOVED HERE] ---
        # تم إزالة كامل المنطق الذي كان يحسب ويطبق الضريبة هنا.

        if is_updated:
            db[user_id] = wallet # Save updates

        return wallet

    except (TypeError, KeyError, AttributeError, ValueError):
        # Create and return a new, default (empty) wallet.
        new_wallet = {item: 0 for item in CURRENCIES}
        new_wallet["last_taxed"] = current_time # <-- [NEW] Set tax time
        db[user_id] = new_wallet
        return new_wallet
