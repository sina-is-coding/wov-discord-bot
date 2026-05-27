from discord.ext import commands
import os
import asyncio
import wolvesville_api as api
from database import always_on_col, members_col
from utils import safe_send_channel, log_event, get_gem_cost

async def questvote_weekly_reminder(bot):
    print("Questvote message should be sent")
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

    await api.send_message_to_clanchat(
            "‼️Neue Woche, neue Quests! Denkt daran, für eure Lieblingsquest(s) abzustimmen! 💝"
        )
    await safe_send_channel(bot.get_channel(int(channel_id)),
            "Questvoting message has been sent in clanchat.")

class Quests(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="queststatus")
    async def quest_status(self, ctx):
        data = await api.get_active_quest()
        if not data:
            await safe_send_channel(ctx.channel, "❌ No quest is currently running.")
            return

        quest = data.get("quest", {})
        tier = data.get("tier", "?")
        finished = data.get("tierFinished", False)
        xp = data.get("xp", 0)
        xp_per = data.get("xpPerReward", 1)
        progress = xp % xp_per if xp_per else 0

        # extracting questname out of image url
        name = os.path.splitext(os.path.basename(quest.get("promoImageUrl", "???")))[0]

        msg = f"""📘 **current quest**
        🧩 name: `{name}`
        ⭐ tier: `{tier + 1}`
        📊 progress: `{progress}/{xp_per}`
        ✅ tier finished? `{"yes" if finished else "no"}`
        """
        await safe_send_channel(ctx.channel, msg)

    @commands.command(name="showquests")
    async def fetch_quests(self, ctx):
        quests = await api.get_available_quests()
        if not quests:
            await safe_send_channel(ctx.channel, "⚠️ No quests available.")
            return
            
        for quest in quests:
            img = quest.get("promoImageUrl", "")
            name = os.path.splitext(os.path.basename(img))[0]
            if img:
                msg = f"📘 **Quest `{name}`**\n{img}"
                await safe_send_channel(ctx.channel, msg)
            else:
                await safe_send_channel(ctx.channel, "⚠️ No image found.")

    @commands.command(name="questactivate")
    @commands.has_role("Leaderteam")
    async def quest_activate(self, ctx, *, args: str = ""):

        parts = args.split()
        force = False
        if "--force" in parts:
            force = True
            parts.remove("--force")
            await safe_send_channel(ctx.channel, "⚠️ Force mode: I will try to activate all voters, even if they don't have enough gold/gems.")

        quest_name = " ".join(parts) if parts else None

        quests = await api.get_available_quests()
        if not quests:
            await safe_send_channel(ctx.channel, "⚠️ No quests available.")
            return

        if quest_name is None:
            quest_list = ""
            for i, quest in enumerate(quests, start=1):
                img = quest.get("promoImageUrl", "")
                name = os.path.splitext(os.path.basename(img))[0]
                quest_list += f"{i}. `{name}`\n"

            await safe_send_channel(ctx.channel,
                f"📘 **Available quests:**\n{quest_list}\n"
                "🔢 Please type the number of the quest you'd like to activate."
            )

            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()

            try:
                msg = await self.bot.wait_for("message", check=check, timeout=30.0)
                index = int(msg.content) - 1
                if index < 0 or index >= len(quests):
                    await safe_send_channel(ctx.channel, "❌ Invalid number. Please try the command again.")
                    return
                matching_quest = quests[index]
            except (asyncio.TimeoutError, TimeoutError):
                await safe_send_channel(ctx.channel, "⌛ Timeout. Please try the command again.")
                return
        else:
            matching_quest = None
            for quest in quests:
                url = quest.get("promoImageUrl", "")
                name = os.path.splitext(os.path.basename(url))[0]
                if name.lower() == quest_name.lower():
                    matching_quest = quest
                    break
            if not matching_quest:
                await safe_send_channel(ctx.channel, f"❌ I couldn't find a quest with the name `{quest_name}`.")
                return

        quest_id = matching_quest.get("id")
        quest_name = os.path.splitext(os.path.basename(matching_quest.get("promoImageUrl", "")))[0]
        
        # fetch voters for this quest
        votes_response = await api.get_votes()
        votes_data = votes_response.get("votes", {})
        voters_ids = votes_data.get(str(quest_id), [])

        # check if its a goldquest
        is_gold_quest = not matching_quest.get("purchasableWithGems", False)

        if is_gold_quest:
            # fetch always on members
            always_on_data = list(always_on_col.find())
            always_on_ids = [member["id"] for member in always_on_data]

            # combine
            participant_ids = list(set(voters_ids + always_on_ids))

        else: 
            participant_ids = voters_ids.copy()
        if not voters_ids:
            await safe_send_channel(ctx.channel, f"⚠️ No one voted for `{quest_name}`.")
            return

        activated = []
        poor_participants = []
        if not is_gold_quest:
            gem_cost = get_gem_cost(len(participant_ids))

        for pid in participant_ids:
            name = await api.fetch_player_name(pid)


            # check the users bank account
            member_data = members_col.find_one({"_id": pid})
            if not member_data:
                poor_participants.append(f"`{name}` (no bank account found)")
                if not force:
                    continue

            # gold quest (500 Gold needed)
            if is_gold_quest:
                balance = member_data.get("balance_gold", 0)

                if balance < 500:
                    poor_participants.append(f"`{name}` ({balance}/500 gold)")
                    if not force:
                        continue
            
            # gem quest (variable costs)
            else:
                balance = member_data.get("balance_gems", 0)

                if balance < gem_cost:
                    poor_participants.append(f"`{name}` ({balance}/{gem_cost} gems)")
                    if not force:
                        continue

            # activate in game
            if await api.change_quest_participation(pid, True):
                activated.append(f"\n`{name}`")

        if activated:
            quest_type = "Gold Quest" if is_gold_quest else "Gem Quest"
            await safe_send_channel(ctx.channel, f"✅ {quest_type} participants for `{quest_name}` activated: {' '.join(activated)}")
        else:
            await safe_send_channel(ctx.channel, f"❌ Error, I couldn't activate for `{quest_name}`.")

        if poor_participants:
            await safe_send_channel(ctx.channel,"⚠️ Not enough balance:\n" + "\n".join(poor_participants))

    @commands.command(name="questdeactivate")
    @commands.has_role("Leaderteam")
    async def quest_deactivate(self, ctx):
        members = await api.get_members()
        if not members:
            await safe_send_channel(ctx.channel, "⚠️ Error fetching members.")
            return

        deactivated = []
        for m in members:
            if m.get("participateInClanQuests"):
                if await api.change_quest_participation(m["playerId"], False):
                    deactivated.append(f"{m.get('username', 'unknown')}")
                await asyncio.sleep(0.2)

        await safe_send_channel(ctx.channel, "I deactivated the following members: " + ", ".join(f"`{name}`" for name in deactivated))

    @commands.command(name="alwaysonlist")
    @commands.has_role("Leaderteam")
    async def always_on_list(self, ctx):

        users = list(always_on_col.find())

        if not users:
            await safe_send_channel(
                ctx.channel,
                "⚠️ The always-on list is empty."
            )
            return

        usernames = [
            user.get("username", "unknown")
            for user in users
        ]

        await safe_send_channel(
            ctx.channel,
            "## Always-on members:\n" +
            "\n".join(f"- {username}" for username in usernames)
        )

    @commands.command(name="setalwayson")
    @commands.has_role("Leaderteam")
    async def set_always_on(self, ctx, username: str):
        # fetch user id to the username
        user = await api.search_player(username)
        if not user:
            await safe_send_channel(
                ctx.channel,
                f"❌ Could not find a player with the username `{username}`."
            )
            return

        # check if the user is part of the clan
        members = await api.get_members()
        is_member = any(member.get("playerId") == user["id"] for member in members)

        if not is_member:
            await safe_send_channel(
                ctx.channel,
                f"⚠️ `{user['username']}` is not in the clan."
            )
            return

        # check if the user is already on the list
        existing_user = always_on_col.find_one({ "id": user["id"]})
        if existing_user:
            await safe_send_channel(
                ctx.channel,
                f"⚠️ `{user['username']}` is already on the always-on list."
            )
            return

        # finally add the user to the list
        always_on_col.insert_one({
            "id": user["id"],
            "username": user["username"]
        })

        await safe_send_channel(
            ctx.channel,
            f"✅ `{user['username']}` has been added to the always-on list."
        )

    @commands.command(name="deletealwayson")
    @commands.has_role("Leaderteam")
    async def delete_always_on(self, ctx, username: str):
        user = await api.search_player(username)
        if not user or user == []:
            await safe_send_channel(ctx.channel, f"❌ Could not find a player with the username `{username}`.")
            return
        result = always_on_col.delete_one({
            "id": user["id"]
        })

        if result.deleted_count == 0:
            await safe_send_channel(
                ctx.channel,
                f"⚠️ `{user['username']}` is not on the always-on list."
            )
            return

        await safe_send_channel(ctx.channel, f"🚮 `{user['username']}` has been removed from the always-on list.")

    @commands.command(name="questvote")
    @commands.has_role("Leaderteam")
    async def quest_vote_reminder(self, ctx):
        questvote_weekly_reminder(self.bot)

    @commands.command(name="questannounce")
    @commands.has_role("Leaderteam")
    async def quest_announcement(self, ctx, questname: str, emotes: str = "🍃📜"):
        message = (
            f"{emotes} {questname.upper()} QUEST {emotes[::-1]}\n\n"
            f"Wir starten am Donnerstagmorgen die {questname} Quest!\n"
            "Wenn ihr mitmachen möchtet, achtet darauf, dass ihr 500 Gold auf eurem Konto habt und ihr für die Quest abgestimmt habt! 💰🪙"   
        )
        await api.send_announcement(message)
        await safe_send_channel(ctx.channel, message)
        await safe_send_channel(ctx.channel,"Announcement sent to clan.")

async def setup(bot):
    await bot.add_cog(Quests(bot))