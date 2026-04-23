import discord
import os
from discord.ext import commands
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone

# loading .env before importing the modules to be able to access the .env in modules
load_dotenv()

# own files/modules
from cogs.milestones import check_for_milestones
from cogs.birthdays import check_todays_birthdays
from cogs.reporting import daily_xp_report
from cogs.quests import questvote_weekly_reminder
from utils import safe_send_channel, log_event



class WovBot(commands.Bot):
    def __init__(self):
        # setting intents
        intents = discord.Intents.default()
        intents.members = True          # reading dc server member list
        intents.message_content = True  # reading message contents
        
        # initialising bot
        super().__init__(
            command_prefix=os.getenv("BOT_PREFIX")+" ", 
            intents=intents,
            help_command=None  # using own help command which is set in cogs
        )
        
        # binding scheduler to bot
        self.scheduler = AsyncIOScheduler(timezone=timezone("UTC"))

    # method is called EXACTLY once for setting up the bot, no repetition after disconnect
    async def setup_hook(self):
        print("--- autoloading modules ---")
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and not filename.startswith('__'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    log_event(f'{filename} loaded successfully.', "success")
                except Exception as e:
                    log_event(f'ERROR at loading {filename}: {e}', "error")

        # setting up schedulers
        """ # sunday 12am: milestone check # NOTE : currently unused
        self.scheduler.add_job(
            check_for_milestones, 
            'cron', 
            day_of_week='sun', 
            hour=12, 
            minute=0,
            args=[self],
            id="milestone_job", 
            replace_existing=True
        )
        
        # daily 9am : birthday check # NOTE : currently unused
        self.scheduler.add_job(
            check_todays_birthdays, 
            'cron', 
            hour=9, 
            minute=0,
            args=[self], 
            id="birthday_job", 
            replace_existing=True
        ) """

        """ daily 7am : xp report # NOTE : currently unused
        self.scheduler.add_job( 
            daily_xp_report, 
            'cron', 
            hour='6',
            minute=0,
            args=[self], 
            id="xp_job", 
            replace_existing=True
        )"""

        # weekly monday questvote reminder
        self.scheduler.add_job(
            questvote_weekly_reminder, 
            'cron', 
            day_of_week='mon', 
            hour=6, 
            minute=1,
            args=[self],
            id="vote_reminder_job", 
            misfire_grace_time=360,
            replace_existing=True
        )
        
        self.scheduler.start()
        log_event("-- Scheduler started --", "success")

    async def on_ready(self):
        log_event(f'🟢 bot is logged in as: {self.user.name} (ID: {self.user.id})', "success")
        allGuilds = ""
        for guild in self.guilds:
            allGuilds += '"'+guild.name+'", '
        log_event(f'{len(self.guilds)} Server(s): {allGuilds}', "info")

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await safe_send_channel(ctx.channel, "❗ This command is missing an argument.")
        elif isinstance(error, commands.MissingRole):
            await safe_send_channel(ctx.channel, "❗ You don't have the required role to use this command.")
        elif isinstance(error, commands.CommandNotFound):
            await safe_send_channel(ctx.channel, "❗ I don't know this command. Use 'help' to see a list of valid commands.")
        else:
            log_event(f'An uncaught error occured: {error}', "error")

if __name__ == "__main__":
    bot = WovBot()
    TOKEN = os.getenv("DISCORD_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        log_event(f'No DISCORD_TOKEN found in .env.', "error")