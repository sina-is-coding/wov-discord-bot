from discord.ext import commands
from pymongo import ReturnDocument

import wolvesville_api as api
from database import members_col, client
from utils import safe_send_channel, log_event

# currency mapping for easier access to fields and emojis
CURRENCIES = {
    "gold": {"field": "balance_gold", "name": "Gold", "emoji": "💰"},
    "gems": {"field": "balance_gems", "name": "Gems", "emoji": "💎"},
}


class Accounts(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _resolve_member(self, ctx, username: str):
        """Fetch player from API and resolve member document from DB."""
        user = await api.search_player(username)
        if not user:
            await safe_send_channel(ctx.channel, f"❌ Player `{username}` not found.")
            return None

        member = members_col.find_one({"_id": user["id"]})
        if not member:
            await safe_send_channel(ctx.channel, f"❌ `{user['username']}` has no account on record.")
            return None

        return member

    async def _modify_single_balance(self, ctx, username: str, currency_key: str, amount: int):
        """Helper to add or remove balance for a user."""
        if amount == 0:
            await safe_send_channel(ctx.channel, "❌ Amount must not be zero.")
            return

        curr = CURRENCIES[currency_key]
        member = await self._resolve_member(ctx, username)
        if not member:
            return

        try:
            updated_member = members_col.find_one_and_update(
                {"_id": member["_id"]},
                {"$inc": {curr["field"]: amount}},
                return_document=ReturnDocument.AFTER
            )

            action = "added to" if amount > 0 else "removed from"
            new_bal = updated_member.get(curr["field"], 0)

            log_event(f"{ctx.author} modified {curr['name']} for {username}: {amount:+}", "success")
            await safe_send_channel(
                ctx.channel,
                f"`{amount:+}` {curr['name']}{curr['emoji']} {action} **{updated_member.get('username', username)}**.\n"
                f"New balance: `{new_bal}`{curr['emoji']}"
            )
        except Exception as e:
            log_event(f"Error in modify_single_balance ({username}): {e}", "error")
            await safe_send_channel(ctx.channel, "❌ Database error updating balance.")

    async def _transfer_currency(self, ctx, from_username: str, to_username: str, currency_key: str, amount: int):
        """Helper to transfer currency between two users using MongoDB transactions."""
        if amount <= 0:
            await safe_send_channel(ctx.channel, "❌ Transfer amount must be greater than zero.")
            return

        curr = CURRENCIES[currency_key]
        sender = await self._resolve_member(ctx, from_username)
        recipient = await self._resolve_member(ctx, to_username)

        if not sender or not recipient:
            return

        if sender["_id"] == recipient["_id"]:
            await safe_send_channel(ctx.channel, "❌ Sender and recipient cannot be the same.")
            return

        # Execute atomic transaction
        try:
            with client.start_session() as session:
                with session.start_transaction():
                    res_sender = members_col.find_one_and_update(
                        {"_id": sender["_id"], curr["field"]: {"$gte": amount}},
                        {"$inc": {curr["field"]: -amount}},
                        return_document=ReturnDocument.AFTER,
                        session=session
                    )

                    if not res_sender:
                        await safe_send_channel(
                            ctx.channel,
                            f"❌ **{sender.get('username')}** does not have enough {curr['name']}! "
                            f"(Available: `{sender.get(curr['field'], 0)}{curr['emoji']}`)"
                        )
                        return

                    res_recipient = members_col.find_one_and_update(
                        {"_id": recipient["_id"]},
                        {"$inc": {curr["field"]: amount}},
                        return_document=ReturnDocument.AFTER,
                        session=session
                    )

            log_event(f"Transfer {curr['name']}: {amount} from {from_username} to {to_username}", "success")
            await safe_send_channel(
                ctx.channel,
                f"`{amount}` {curr['name']} {curr['emoji']} transferred from **{sender.get('username')}** to **{recipient.get('username')}**!\n"
                f"**{sender.get('username')}**'s remaining balance: `{res_sender.get(curr['field'], 0)}{curr['emoji']}`\n"
                f"**{recipient.get('username')}**'s new balance: `{res_recipient.get(curr['field'], 0)}{curr['emoji']}`"
            )
        except Exception as e:
            log_event(f"Transfer failed ({from_username} -> {to_username}): {e}", "error")
            await safe_send_channel(ctx.channel, "❌ Transaction failed. No balances were changed.")

    # --- COMMANDS ---

    @commands.command(name="balance")
    async def show_balance(self, ctx, username: str):
        """Display player's balance."""
        member = await self._resolve_member(ctx, username)
        if not member:
            return

        await safe_send_channel(
            ctx.channel,
            f"## {member.get('username', username)}'s Schätze 🍃\n"
            f"{CURRENCIES['gems']['emoji']} `{member.get(CURRENCIES['gems']['field'], 0)}`\n"
            f"{CURRENCIES['gold']['emoji']} `{member.get(CURRENCIES['gold']['field'], 0)}`"
        )

    @commands.command(name="addgold")
    @commands.has_role("Leaderteam")
    async def add_gold(self, ctx, username: str, amount: int):
        if amount <= 0:
            await safe_send_channel(ctx.channel, "❌ Amount must be greater than zero.")
            return

        await self._modify_single_balance(ctx, username, "gold", amount)

    @commands.command(name="removegold")
    @commands.has_role("Leaderteam")
    async def remove_gold(self, ctx, username: str, amount: int):
        if amount <= 0:
            await safe_send_channel(ctx.channel, "❌ Amount must be greater than zero.")
            return

        await self._modify_single_balance(ctx, username, "gold", -amount)

    @commands.command(name="addgems")
    @commands.has_role("Leaderteam")
    async def add_gems(self, ctx, username: str, amount: int):
        if amount <= 0:
            await safe_send_channel(ctx.channel, "❌ Amount must be greater than zero.")
            return

        await self._modify_single_balance(ctx, username, "gems", amount)

    @commands.command(name="removegems")
    @commands.has_role("Leaderteam")
    async def remove_gems(self, ctx, username: str, amount: int):
        if amount <= 0:
            await safe_send_channel(ctx.channel, "❌ Amount must be greater than zero.")
            return

        await self._modify_single_balance(ctx, username, "gems", -amount)

    # Transfers
    @commands.command(name="transfergold")
    @commands.has_role("Leaderteam")
    async def transfer_gold(self, ctx, from_username: str, to_username: str, amount: int):
        await self._transfer_currency(ctx, from_username, to_username, "gold", amount)

    @commands.command(name="transfergems")
    @commands.has_role("Leaderteam")
    async def transfer_gems(self, ctx, from_username: str, to_username: str, amount: int):
        await self._transfer_currency(ctx, from_username, to_username, "gems", amount)


async def setup(bot):
    await bot.add_cog(Accounts(bot))