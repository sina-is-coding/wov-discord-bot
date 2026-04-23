import os
import wolvesville_api as api
from discord.ext import commands
import re
from utils import safe_send_channel, log_event


# NOTE: This Cog is currently not in use,  since it's not needed. Adding a weekly/monthly xp and donations-Report is on the TODO-List though


async def daily_xp_report(bot):
    
    channel_id = os.getenv("BOT_CHANNEL_ID")
    if not channel_id:
        log_event("BOT_CHANNEL_ID missing in .env", "error")
        return

    channel = bot.get_channel(int(channel_id))
    if not channel:
        try:
            channel = await bot.fetch_channel(int(channel_id))
        except Exception as e:
            log_event(f"Could not find bot channel: {e}", "error")
            return

    # fetch current clan xp
    data = await api.get_clan_info()
    if data:
        alltimexp = int(data.get("xp", 0))

        # get last xp from last bot message
        last_xp = 0
        async for message in channel.history(limit=100):
            if message.author == bot.user and "Current clan xp:" in message.content:
                match = re.search(r"clan xp:\**\s*`([\d.]+)`", message.content)
                if match:
                    last_xp = int(match.group(1).replace(".", ""))
                    break

        # calc difference
        diff = alltimexp - last_xp if last_xp > 0 else 0
        
        def format(n): return f"{n:,}".replace(",", ".")
        
        diff_text = f" (+{format(diff)}xp)" if diff > 0 else ""
        
        msg = (
            f"## Daily Clan Xp Check\n"
            f"**Current clan xp:** `{format(alltimexp)}`{diff_text}\n"
        )
    else:
        msg = "Couldn't fetch current clan xp."

    await safe_send_channel(channel, msg)

class Reporting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="disablereport")
    async def disable_breporting_scheduler(self, ctx):
        # TODO !! 
        await safe_send_channel(ctx.channel, f"This function is not available yet, sorry!")

    @commands.command(name="enablereport")
    async def enable_reporting_scheduler(self, ctx):
        # TODO !! 
        await safe_send_channel(ctx.channel, f"This function is not available yet, sorry!")

    @commands.command(name="getxp")
    @commands.has_role("Leaderteam")
    async def manual_report(self, ctx):
        await daily_xp_report(self.bot)

async def setup(bot):
    await bot.add_cog(Reporting(bot))