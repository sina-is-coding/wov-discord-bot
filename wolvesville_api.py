import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("WOLVESVILLE_API_KEY")
CLAN_ID = os.getenv("CLAN_ID")

HEADERS = {
    "Authorization": f"Bot {API_KEY}",
    "Content-Type": "application/json"
}
BASE_URL = f"https://api.wolvesville.com/clans/{CLAN_ID}"

async def fetch(url, method="GET", json_data=None):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.request(method, url, headers=HEADERS, json=json_data) as res:
                if res.status == 200:
                    return await res.json()
                return None
        except Exception as e:
            print(f"API Error: {e}")
            return None

async def get_active_quest():
    return await fetch(f"{BASE_URL}/quests/active")

async def get_votes():
    return await fetch(f"{BASE_URL}/quests/votes") or {}

async def get_available_quests():
    return await fetch(f"{BASE_URL}/quests/available") or []

async def get_members():
    return await fetch(f"{BASE_URL}/members") or []

async def change_quest_participation(player_id, value: bool):
    url = f"{BASE_URL}/members/{player_id}/participateInQuests"
    res = await fetch(url, method="PUT", json_data={"participateInQuests": value})
    return res.get("participateInClanQuests") == value if res else False

async def fetch_player_name(player_id):
    res = await fetch(f"https://api.wolvesville.com/players/{player_id}")
    return res.get("username", "Unknown") if res else "Unknown"

async def get_clan_info():
    return await fetch(f"{BASE_URL}/info")

async def send_message_to_clanchat(message):
    url = f"{BASE_URL}/chat"
    await fetch(url, method="POST", json_data={"message": message})

async def send_announcement(message):
    url = f"{BASE_URL}/announcements"
    res = await fetch(url, method="POST", json_data={"message": message})
    return res