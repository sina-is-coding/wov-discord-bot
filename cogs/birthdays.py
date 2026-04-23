import discord
from discord.ext import commands
from discord.ui import View, Button
from datetime import datetime
from pytz import timezone
from database import birthdays_col
from utils import safe_send_channel, parse_birthday, log_event
import os

# Konfiguration
BIRTHDAY_CHANNEL_ID = int(os.getenv("BIRTHDAY_CHANNEL_ID"))
BOT_CHANNEL_ID = int(os.getenv("BOT_CHANNEL_ID"))

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December"
}

def build_birthday_list():
    """Building the formatted string for the birthday list"""
    all_birthdays = list(birthdays_col.find())
    birthdays_by_month = {m: [] for m in range(1, 13)}

    for entry in all_birthdays:
        day, month = parse_birthday(entry["birthday"])
        if month:
            birthdays_by_month[month].append((day, entry["user_id"], entry["name"]))

    lines = [f"# Birthdays 🎈"]
    for month in range(1, 13):
        if birthdays_by_month[month]:
            lines.append(f"## {MONTH_NAMES[month]}")
            sorted_days = sorted(birthdays_by_month[month], key=lambda x: (x[0] if x[0] is not None else 99))
            for day, user_id, name in sorted_days:
                date_str = f"{MONTH_NAMES[month]} {day:02d}" if day else f"{MONTH_NAMES[month]}"
                lines.append(f"✨ **{date_str}** – <@{user_id}> *({name})*")
            lines.append("")
    
    return "\n".join(lines) if len(lines) > 1 else "No birthdays found."

class BirthdayView(View):
    """adding a view to keep the bdlist refresh button alive"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔄", style=discord.ButtonStyle.secondary, custom_id="refresh_birthday_button")
    async def refresh_button(self, interaction: discord.Interaction, button: Button):
        new_content = build_birthday_list()
        await interaction.response.edit_message(content=new_content, view=self)

class Birthdays(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="bdlist")
    async def list_birthdays(self, ctx):
        await safe_send_channel(ctx.channel, build_birthday_list(), view=BirthdayView())

    @commands.command(name="bdmonth")
    async def birthday_month(self, ctx, month: int):
        if month is None or not 1 <= month <= 12:
            await safe_send_channel(ctx.channel, "Please use 1–12 to specify a month.")
            return

        all_birthdays = list(birthdays_col.find())
        month_birthdays = []
        for entry in all_birthdays:
            day, m = parse_birthday(entry["birthday"])
            if m == month:
                month_birthdays.append((day, entry["user_id"], entry["name"]))

        if not month_birthdays:
            await safe_send_channel(ctx.channel, f"No birthdays found in {MONTH_NAMES[month]}.")
            return

        lines = [f"# Birthdays in {MONTH_NAMES[month]}:"]
        for day, user_id, name in sorted(month_birthdays, key=lambda x: (x[0] if x[0] else 99)):
            date_str = f"{MONTH_NAMES[month]} {day:02d}" if day else f"{MONTH_NAMES[month]}"
            lines.append(f"🎉 **{date_str}** – <@{user_id}> *({name})*")
        await safe_send_channel(ctx.channel, "\n".join(lines))

    @commands.command(name="addbd")
    @commands.has_role("Leaderteam")
    async def add_birthday(self, ctx, user_input: str, birthday: str):
        """
        Adding a birthday.
        Works either with @Mention or a UserID.
        """
        user_id = None
        display_name = None

        clean_id = user_input.strip("<@!>")
        
        if clean_id.isdigit():
            user_id = clean_id
            # getting the username from the current server
            member = ctx.guild.get_member(int(user_id))
            if member:
                display_name = member.display_name
            else:
                # getting the global username (if user not found on server)
                try:
                    user_obj = await self.bot.fetch_user(int(user_id))
                    display_name = user_obj.name
                # last resort: user id
                except:
                    display_name = f"User {user_id}"
        
        if not user_id:
            await safe_send_channel(ctx.channel, "⚠️ Please use either a UserID or a @Mention to add a birthday.")
            return

        # DB save / update
        doc = {
            "user_id": str(user_id),
            "name": display_name,
            "birthday": birthday
        }
        birthdays_col.update_one({"user_id": doc["user_id"]}, {"$set": doc}, upsert=True)
        await safe_send_channel(ctx.channel, f"🎉 Birthday for {display_name} added on `{birthday}`!")

    @commands.command(name="delbd")
    @commands.has_role("Leaderteam")
    async def delete_birthday(self, ctx, user_input: str):
        """
        deleting a bday
        works either with @Mention or a UserID.
        """

        user_id = user_input.strip("<@!>")

        if not user_id.isdigit():
            await safe_send_channel(ctx.channel, "⚠️ Please use either a UserID or a @Mention to delete a birthday.")
            return

        result = birthdays_col.delete_one({"user_id": str(user_id)})
        
        if result.deleted_count:
            await safe_send_channel(ctx.channel, f"🗑️ Birthday for <@{user_id}> has been removed.")
        else:
            await safe_send_channel(ctx.channel, f"⚠️ No birthday found for `{user_id}`")

    @commands.command(name="updatebd")
    @commands.has_role("Leaderteam")
    async def sync_birthdays(self, ctx):
        """
        syncing bdays
        - update server nicknames
        - alert if a user left the server
        """
        all_birthdays = list(birthdays_col.find())
        updated = 0
        missing_users = []

        for entry in all_birthdays:
            member = ctx.guild.get_member(int(entry["user_id"]))
            if member:
                # update nick in db
                if entry.get("name") != member.display_name:
                    birthdays_col.update_one(
                        {"user_id": entry["user_id"]}, 
                        {"$set": {"name": member.display_name}})
                    updated += 1
            else:
                # user not on the server
                missing_users.append(entry)

        lines = [f"🔄 Everything is on sync! {updated} Nicknames changed."]
        if missing_users:
            lines.append("⚠️ Users that left the server:\n")
            for entry in missing_users:
                lines.append(f"- `{entry['user_id']}` (*{entry['name']}*)")
            lines.append("🍰 Use `delbd <userid>` to remove their birthdays.")
        await safe_send_channel(ctx.channel, "\n".join(lines))

    @commands.command(name="checkbd")
    @commands.has_role("Leaderteam")
    async def check_bd_manual(self, ctx):
        await safe_send_channel(ctx.channel, "😏 Starting manual birthday-check...")
        await check_todays_birthdays(self.bot)
        await safe_send_channel(ctx.channel, "✅ Birthday-check done")


async def check_todays_birthdays(bot):
    now = datetime.now(timezone("UTC"))
    day, month = now.day, now.month

    for guild in bot.guilds:
        birthday_channel = guild.get_channel(BIRTHDAY_CHANNEL_ID)
        bot_channel = guild.get_channel(BOT_CHANNEL_ID)
        if not bot_channel:
            log_event(f"Bot channel missing in {guild.name}", "error")
            continue
        if not birthday_channel:
            await safe_send_channel(bot_channel, f"⚠️ Could not find birthday channel {BIRTHDAY_CHANNEL_ID} in {guild.name}")
            continue
        
        # fetch all birthdays from DB
        all_birthdays = list(birthdays_col.find())
        for entry in all_birthdays:
            b_day, b_month = parse_birthday(entry["birthday"])
            #check with current date
            if b_day == day and b_month == month:
                user_id = int(entry["user_id"])
                member = guild.get_member(user_id)
                
                display_name = member.display_name if member else entry.get("name", "Someone")
                mention = member.mention if member else f"<@{user_id}>"
                avatar_url = member.display_avatar.url if member else None

                embed = discord.Embed(
                    title=f"HAPPY BIRTHDAY {display_name}! 🥳🎈",
                        description=f"🎶 Happy Birthday to You! Happy Birthday to You! Happy Birthday dear {mention}... **HAPPY BIRTHDAY TO YOU!!!** 🎶 \nWe hope you enjoy your special day!",
                        color=discord.Colour.fuchsia()
                )
                if avatar_url:
                    embed.set_thumbnail(url=avatar_url)
                
                await safe_send_channel(birthday_channel, content=mention, embed=embed)

async def setup(bot):
    bot.add_view(BirthdayView()) # register view for functionality after restarting the bot
    await bot.add_cog(Birthdays(bot))