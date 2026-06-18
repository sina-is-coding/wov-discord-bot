import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()

def get_headers():
    """Generates fresh headers to avoid caching old API keys from .env."""
    return {
        "Authorization": f"Bot {os.getenv('WOLVESVILLE_API_KEY')}",
        "Content-Type": "application/json"
    }

def get_base_url():
    """Generates the base URL dynamically based on CLAN_ID."""
    return f"https://api.wolvesville.com/clans/{os.getenv('CLAN_ID')}"

async def fetch(url, method="GET", json_data=None):
    async with aiohttp.ClientSession() as session:
        # raise_for_status throws an exception on bad HTTP codes (e.g., 401, 403, 500)
        async with session.request(method, url, headers=get_headers(), json=json_data) as res:
            res.raise_for_status()
            
            # Read content type to safely return JSON or empty dictionaries
            if res.status in [200, 201]:
                if res.content_type == "application/json":
                    return await res.json()
                return {"success": True}
            return None

async def get_active_quest():
    try: return await fetch(f"{get_base_url()}/quests/active")
    except Exception: return None

async def get_votes():
    try: return await fetch(f"{get_base_url()}/quests/votes") or {}
    except Exception: return {}

async def get_available_quests():
    try: return await fetch(f"{get_base_url()}/quests/available") or []
    except Exception: return []

async def get_members():
    try: return await fetch(f"{get_base_url()}/members") or []
    except Exception: return []

async def change_quest_participation(player_id, value: bool):
    try:
        url = f"{get_base_url()}/members/{player_id}/participateInQuests"
        res = await fetch(url, method="PUT", json_data={"participateInQuests": value})
        return res.get("participateInClanQuests") == value if res else False
    except Exception:
        return False

async def fetch_player_name(player_id):
    try:
        res = await fetch(f"https://api.wolvesville.com/players/{player_id}")
        return res.get("username", "Unknown") if res else "Unknown"
    except Exception:
        return "Unknown"

async def get_clan_info():
    try: return await fetch(f"{get_base_url()}/info")
    except Exception: return None

async def send_message_to_clanchat(message):
    try:
        url = f"{get_base_url()}/chat"
        await fetch(url, method="POST", json_data={"message": message})
    except Exception:
        pass

async def send_announcement(message):
    url = f"{get_base_url()}/announcements"
    return await fetch(url, method="POST", json_data={"message": message})

async def search_player(username):
    try: return await fetch(f"https://api.wolvesville.com/players/search?username={username}") or []
    except Exception: return []