from discord.ext import commands
import os
import asyncio
import wolvesville_api as api
from database import events_col
from utils import safe_send_channel, log_event, get_gem_cost
from ui.event_elements import EventAnnounceView

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(name="eventannounce")
    @commands.has_role("Leaderteam")
    async def quest_announcement(self, ctx):
        view = EventAnnounceView(
            ctx=ctx, 
            api_client=api, 
            db_collection=events_col, 
        )
    
        embed = view.get_initial_embed()
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Events(bot))