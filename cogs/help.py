from discord.ext import commands
from utils import safe_send_channel
import os

prefix = os.getenv("BOT_PREFIX")

import discord
from discord.ext import commands
from utils import safe_send_channel
import os

prefix = os.getenv("BOT_PREFIX")

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help")
    async def help_command(self, ctx):
        embed = discord.Embed(
            title="🆘 Help",
            description=f"All commands must be used with the `{prefix}` prefix.",
            color=discord.Color.from_rgb(162, 155, 254)
        )
        # quests
        embed.add_field(
            name="🎟 Quests",
            value=(
                f"`{prefix} queststatus` - shows active quest\n"
                f"`{prefix} showquests` - lists available quests\n"
                f"`{prefix} questactivate` - activate voters 🎖️\n"
                f"`{prefix} questdeactivate` - deactivate all 🎖️\n"
                f"`{prefix} questvote <message>` - clanchat reminder for new quests 🎖️\n"
                f"`{prefix} questannounce <questname> [emotes]` - announce a quest 🎖️\n"
            ),
            inline=False
        )
        # birthdays
        embed.add_field(
            name="🍾 Birthdays",
            value=(
                f"`{prefix} bdlist` - shows all\n"
                f"`{prefix} bdmonth <1-12>` - shows in specific month\n"
                f"`{prefix} addbd @user <DD.MM>` - add/update 🎖️\n"
                f"`{prefix} delbd @user` - delete 🎖️\n"
                f"`{prefix} updatebd` - sync nicknames/left 🎖️\n"
                f"`{prefix} checkbd` - manual check for todays birthdays"
            ),
            inline=False
        )

        # milestones
        # embed.add_field(
        #    name="🎉 Milestones",
        #    value=(
        #        f"`{prefix} milestones` -  manual check for new milestones"
        #    ),
        #    inline=False
        #)'''

        # scheduler
        #embed.add_field(
        #    name="🚩 Automation",
        #    value="automatic checks for **Birthdays** (Daily) & **Milestones** (Sundays).",
        #    inline=False
        #)

        # footer
        embed.set_footer(text="🎖️ = Leaderteam only | Powered by pokemosh")
        
        await safe_send_channel(ctx.channel, embed=embed)

async def setup(bot):
    await bot.add_cog(General(bot))