import os
from pymongo import MongoClient
from dotenv import load_dotenv


load_dotenv()
client = MongoClient(os.getenv("MONGO_URI"), connect=False)
db = client[os.getenv("DB_NAME")]

# ==================================================
# COLLECTIONS
# ==================================================

# Birthdays
# Stores Discord Server members birthdays
    # Fields:
    # - user_id (string): Discord user ID
    # - birthday (string): birthday in format 01.12  (i know it's weird lol)
    # - name (string): Server nickname
        # Example: 
        #       {
        #        "user_id": "123456789012345678",
        #        "birthday": "06.06",
        #        "name": "pokemosh"
        #        }

birthdays_col = db["birthdays"]

# ==================================================
# Settings
# Stores global bot configuration
# Currently unused / empty
settings_col = db["settings"]

# ==================================================
# Quests
# Stores Wolvesville quest plan entries
# Fields:
# - kw (int): Calendar week
# - day (string): Day of week
# - name (string): Wolvesville quest name
# - display_name (string): User-facing quest name
# - type (string): Reward type ("gems" or "gold")
# - emoji (string): Reward type emoji (💎 / 💰)
        # Example: 
        #       {
        #       "kw": 15,
        #       "day": "Donnerstag",
        #       "name": "killercircus",
        #       "display_name": "Killer Circus 🃏🔥",
        #       "type": "gold",
        #       "emoji": "💰"
        #       }
quests_col = db["quests"]

# ==================================================
# Members
# Stores clan member balances
# Fields:
# - _id (string) : Wolvesville User id
# - balance_gems (int): Gem balance
# - balance_gold (int): Gold balance
# - is_active (bool): Whether the user is an active clan member (changes to "false" when a user leaves the clan)
# - username (string): Wolvesville username
        # Example: 
        #       {
        #       "_id": "abcdefgh-ijkl-mnop-qrst-uvwxyz123456",
        #       "balance_gems": 300,
        #       "balance_gold": 1500,
        #       "is_active": true,
        #       "username": "pokemosh"
        #       }
members_col = db["members"]
# ==================================================


# ==================================================
# Always on
# Stores data for clanmembers, that wish to be activated for every goldquest
# Fields:
# - id (string) : Wolvesville User id
# - username (string): Wolvesville username
        # Example: 
        #       {
        #       "id": "abcdefgh-ijkl-mnop-qrst-uvwxyz123456",
        #       "username": "pokemosh"
        #       }
always_on_col = db["always_on_members"]
# ==================================================
