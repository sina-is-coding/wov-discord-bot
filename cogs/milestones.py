import discord
from discord.ext import commands
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pytz import timezone
import asyncio
import os
from utils import safe_send_channel

MILESTONE_CHANNEL_ID = int(os.getenv("MILESTONE_CHANNEL_ID"))
BOT_CHANNEL_ID = int(os.getenv("BOT_CHANNEL_ID"))

class Milestones(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="milestones")
    @commands.has_role("Leaderteam")
    async def milestone_check_manual(self, ctx):
        await safe_send_channel(ctx.channel, "😏 Starting manual Milestone-Check...")
        await check_for_milestones(self.bot, ctx.channel)

async def check_for_milestones(bot, current_channel=None):
    now = datetime.now(timezone("UTC"))

    for guild in bot.guilds:
        clan_role = discord.utils.get(guild.roles, name="clan members")
        big_role = discord.utils.get(guild.roles, name="big nub")
        mega_role= discord.utils.get(guild.roles, name="mega nub")
        pro_role = discord.utils.get(guild.roles, name="pros")
        legend_role = discord.utils.get(guild.roles, name="legends")

        roles = {
            "clan members": clan_role,
            "big nub": big_role,
            "mega nub": mega_role,
            "pros": pro_role,
            "legends": legend_role
        }
        if current_channel:
            bot_channel = current_channel
        else:
            bot_channel = guild.get_channel(BOT_CHANNEL_ID)

        await safe_send_channel(bot_channel, f"🔍 Milestone-check in {guild.name} starting...")

        # check if the roles exist
        missing_roles = [name for name, role in roles.items() if role is None]
        if missing_roles:
            await bot_channel.send(f"⚠️ Couldn't find roles {missing_roles} in {guild.name}")
            continue

        # check announcement channel
        announce_channel = guild.get_channel(MILESTONE_CHANNEL_ID)
        if not announce_channel:
            await safe_send_channel(bot_channel, f"⚠️ Couldn't find the milestone channel {MILESTONE_CHANNEL_ID} in {guild.name}")
            continue
        
        updated = []
        for member in clan_role.members:
            if not member.joined_at:
                continue

            delta = relativedelta(now, member.joined_at)
            months = delta.years * 12 + delta.months

            milestone_messages = {
                "💪 BIG NUB": "{mention} is now a 💪**BIG NUB!!** \nCongrats on your first 3 months on here!",
                "🏆 MEGA NUB": "{mention} is now a 🏆**MEGA NUB!!** \nYou're leaving a trail of magic, everywhere you go! Congrats on 6 months with us!!",
                "🎖️ PRO": "{mention} ís now a 🎖️**PRO!!**\n Magical productivity, guaranteed! Congrats on being here for the last 9 months!! ",
                "👑 LEGEND": "{mention} is now a 👑**LEGEND!!** \nNot only are you mythical and magical, but now you're totally legendary!! Thank you for being here for the past year!!"
            }

            milestones = [
                (3, big_role, "💪 BIG NUB"),
                (6, mega_role, "🏆 MEGA NUB"),
                (9, pro_role, "🎖️ PRO"),
                (12, legend_role, "👑 LEGEND"),
            ]

            for limit, role, label in milestones:
                if role and months >= limit and role not in member.roles:
                    await member.add_roles(role)
                    updated.append(f"{label}: {member.nick} ({months} months)")

                    message = milestone_messages.get(label, f"🎉 {member.mention} reached **{label}**!")
                
                    # Embed
                    embed = discord.Embed(
                        title=f"A New {label} has appeared! 🤩",
                        description=message.format(mention=member.mention),
                        color=role.color,
                        timestamp=datetime.utcnow()
                    )
                    embed.set_footer(text=f"{member.nick} • {months} months with us")

                    await safe_send_channel(announce_channel, embed=embed)

        if updated:
            msg = "\n".join(updated)
            await safe_send_channel(bot_channel, f"## Updated milestones \n{msg}")
        else:
            await safe_send_channel(bot_channel, "👀 No new milestones this week.")

        await safe_send_channel(bot_channel, "✅ Milestone-check finished.")
        
async def setup(bot):
    await bot.add_cog(Milestones(bot))