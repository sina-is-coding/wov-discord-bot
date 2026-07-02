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
BOT_PREFIX = os.getenv("BOT_PREFIX", "!")

MONTH_NAMES = {
    1: "Januar", 2: "Februar", 3: "März", 4: "April",
    5: "Mai", 6: "Juni", 7: "Juli", 8: "August",
    9: "September", 10: "Oktober", 11: "November", 12: "Dezember"
}

def build_birthday_list():
    """Building the formatted string for the birthday list"""
    all_birthdays = list(birthdays_col.find())
    birthdays_by_month = {m: [] for m in range(1, 13)}

    for entry in all_birthdays:
        day, month = parse_birthday(entry["birthday"])
        if month:
            birthdays_by_month[month].append((day, entry["user_id"], entry["name"]))

    lines = [f"# Geburtstage"]
    for month in range(1, 13):
        if birthdays_by_month[month]:
            lines.append(f"## {MONTH_NAMES[month]}")
            sorted_days = sorted(birthdays_by_month[month], key=lambda x: (x[0] if x[0] is not None else 99))
            for day, user_id, name in sorted_days:
                date_str = f"{day:02d}. {MONTH_NAMES[month]}" if day else f"{MONTH_NAMES[month]}"
                lines.append(f"**{date_str}** – <@{user_id}> *({name})*")
            lines.append("")
    
    return "\n".join(lines) if len(lines) > 1 else "Keine Geburtstage gefunden."

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
            await safe_send_channel(ctx.channel, "Bitte nutze die Zahlen 1–12, um einen Monat anzugeben.")
            return

        all_birthdays = list(birthdays_col.find())
        month_birthdays = []
        for entry in all_birthdays:
            day, m = parse_birthday(entry["birthday"])
            if m == month:
                month_birthdays.append((day, entry["user_id"], entry["name"]))

        if not month_birthdays:
            await safe_send_channel(ctx.channel, f"Keine Geburtstage im {MONTH_NAMES[month]} gefunden.")
            return

        lines = [f"# Geburtstage im {MONTH_NAMES[month]}:"]
        for day, user_id, name in sorted(month_birthdays, key=lambda x: (x[0] if x[0] else 99)):
            date_str = f"{day:02d}. {MONTH_NAMES[month]}" if day else f"{MONTH_NAMES[month]}"
            lines.append(f"**{date_str}** – <@{user_id}> *({name})*")
        await safe_send_channel(ctx.channel, "\n".join(lines))

    @commands.command(name="addbd")
    async def add_birthday(self, ctx, *args):
        """
        Adding a birthday.
        Leaderteam: addbd @Mention/ID 01.06.
        User for themselves: addbd 01.06
        """
        if len(args) == 2:
            # leader command
            if not any(role.name == "Leaderteam" for role in ctx.author.roles):
                await safe_send_channel(ctx.channel, "Du hast keine Berechtigung, Geburtstage für andere einzutragen.")
                return
            user_input = args[0]
            birthday_input = args[1]
        elif len(args) == 1:
            # normal user command
            user_input = str(ctx.author.id)
            birthday_input = args[0]
        else:
            await safe_send_channel(ctx.channel, f"Da ist was schief gegangen! \nUm deinen Geburtstag einzutragen, schreibe: `{BOT_PREFIX} addbd 01.06.`")
            return

        birthday = birthday_input.rstrip(".") # remove the last . for parsing the birthday
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
            await safe_send_channel(ctx.channel, "Bitte nutze entweder eine UserID oder eine @Mention, um einen Geburtstag hinzuzufügen.")
            return

        # DB save / update
        doc = {
            "user_id": str(user_id),
            "name": display_name,
            "birthday": birthday
        }
        birthdays_col.update_one({"user_id": doc["user_id"]}, {"$set": doc}, upsert=True)
        await safe_send_channel(ctx.channel, f"Geburtstag für {display_name} am `{birthday}.` wurde gespeichert!")

    @commands.command(name="delbd")
    async def delete_birthday(self, ctx, user_input: str = None):
        """
        deleting a bday
        Leader: !delbd @Mention/ID
        User: !delbd
        """

        if user_input is None: # normal user
            user_id = str(ctx.author.id)
        else: # leader command
            if not any(role.name == "Leaderteam" for role in ctx.author.roles):
                await safe_send_channel(ctx.channel, f"Du darfst nur deinen eigenen Geburtstag löschen (nutze einfach `{BOT_PREFIX} delbd`).")
                return
            user_id = user_input.strip("<@!>")

        if not user_id.isdigit():
            await safe_send_channel(ctx.channel, "Ungültige User-ID oder Mention.")
            return

        result = birthdays_col.delete_one({"user_id": str(user_id)})
        
        if result.deleted_count:
            if user_input is None:
                await safe_send_channel(ctx.channel, f"Dein Geburtstag wurde gelöscht, <@{user_id}>.")
            else:
                await safe_send_channel(ctx.channel, f"Geburtstag für <@{user_id}> wurde vom Leaderteam entfernt.")
        else:
            await safe_send_channel(ctx.channel, f"Kein Geburtstag für <@{user_id}> in der Datenbank gefunden.")

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

        lines = [f"Alles ist synchronisiert! {updated} Nicknames wurden geändert."]
        if missing_users:
            lines.append("Benutzer, die den Server verlassen haben:\n")
            for entry in missing_users:
                lines.append(f"- `{entry['user_id']}` (*{entry['name']}*)")
            lines.append(f"Nutze `{BOT_PREFIX} delbd <userid>`, um deren Geburtstage zu entfernen.")
        await safe_send_channel(ctx.channel, "\n".join(lines))

    @commands.command(name="checkbd")
    @commands.has_role("Leaderteam")
    async def check_bd_manual(self, ctx):
        await safe_send_channel(ctx.channel, "Manuelle Geburtstagsprüfung wird gestartet...")
        await check_todays_birthdays(self.bot)
        await safe_send_channel(ctx.channel, "Geburtstagsprüfung abgeschlossen.")


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
            await safe_send_channel(bot_channel, f"Der Geburtstagskanal {BIRTHDAY_CHANNEL_ID} konnte in {guild.name} nicht gefunden werden.")
            continue
        
        # fetch all birthdays from DB
        all_birthdays = list(birthdays_col.find())
        for entry in all_birthdays:
            b_day, b_month = parse_birthday(entry["birthday"])
            #check with current date
            if b_day == day and b_month == month:
                user_id = int(entry["user_id"])
                member = guild.get_member(user_id)
                
                display_name = member.display_name if member else entry.get("name", "Jemand")
                mention = member.mention if member else f"<@{user_id}>"
                avatar_url = member.display_avatar.url if member else None

                embed = discord.Embed(
                    title=f"ALLES GUTE ZUM GEBURTSTAG, {display_name}!",
                    description=f"Happy Birthday to You! Happy Birthday to You! Happy Birthday liebe/r {mention}... **HAPPY BIRTHDAY TO YOU!!!** \n\nAlles Liebe zum Geburtstag, genieße deinen Tag!",
                    color=discord.Colour.green()
                )
                if avatar_url:
                    embed.set_thumbnail(url=avatar_url)
                
                await safe_send_channel(birthday_channel, content=mention, embed=embed)

async def setup(bot):
    bot.add_view(BirthdayView()) # register view for functionality after restarting the bot
    await bot.add_cog(Birthdays(bot))