import asyncio
import discord

async def safe_send_channel(channel, content=None, retries=2, **kwargs):
    """
    Sending messages in given channels safely & catches rate-limits
    """
    if not channel:
        return None
        
    for attempt in range(retries):
        try:
            return await channel.send(content=content, **kwargs)
        except discord.HTTPException as e:
            if e.status == 429:  
                wait_time = 5 + attempt * 2
                log_event(f'rate-limit was being hit... waiting {wait_time}s...', "error")
                await asyncio.sleep(wait_time)
            else:
                log_event(f'Safe sending failed: {e}', "error")
                break
    return None

def parse_birthday(bd_str):
    """
    Changing '01.08' ar 'XX.06' to date format (day, month)
    """
    try:
        day_part, month_part = bd_str.split(".")
        day = int(day_part) if day_part.isdigit() else None
        month = int(month_part)
        return day, month
    except ValueError:
        return None, None

def log_event(message, level="info"):
    colors = {
        "info": "\033[94m",    # blue
        "success": "\033[92m", # green
        "warning": "\033[93m", # yellow
        "error": "\033[91m",   # red
        "reset": "\033[0m"
    }
    color = colors.get(level, colors["reset"])
    print(f"{color}[{level.upper()}] {message}{colors['reset']}")

def get_gem_cost(participants: int) -> int:
    if participants <= 3:
        return 255
    elif participants == 4:
        return 225
    elif participants == 5:
        return 205
    elif participants == 6:
        return 195
    elif participants == 7:
        return 185
    elif participants == 8:
        return 180
    elif participants == 9:
        return 175
    elif participants <= 11:
        return 170
    elif participants <= 13:
        return 165
    else:
        return 160