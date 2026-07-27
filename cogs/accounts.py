import discord
from discord.ext import commands
import wolvesville_api as api
from database import members_col
from utils import safe_send_channel, log_event

CURRENCY_FIELDS = {
    "gems": "balance_gems",
    "gold": "balance_gold",
}

def resolve_currency(currency: str):
    return CURRENCY_FIELDS.get(currency.lower().strip())


class Accounts(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _resolve_member(self, ctx, username: str):
        # Resolve a Wolvesville username to its members_col document.
        # Returns the member doc, or None (and sends an error message) if it can't be found.
        user = await api.search_player(username)
        if not user:
            await safe_send_channel(
                ctx.channel,
                f"❌ Could not find a player with the username `{username}`."
            )
            return None

        member = members_col.find_one({"_id": user["id"]})
        if not member:
            await safe_send_channel(
                ctx.channel,
                f"⚠️ `{user['username']}` has no account on record."
            )
            return None

        return member

    async def _parse_changes(self, ctx, changes, usage):
        # Parse variadic <currency> <amount> pairs into a {field: amount} dict.
        # Returns the dict, or None (and sends an error message) if anything is malformed.
        if not changes or len(changes) % 2 != 0:
            await safe_send_channel(ctx.channel, usage)
            return None

        deltas = {}
        for currency, raw_amount in zip(changes[0::2], changes[1::2]):
            field = resolve_currency(currency)
            if not field:
                await safe_send_channel(ctx.channel, f"❌ Invalid currency `{currency}`. Use `gems` or `gold`.")
                return None
            if field in deltas:
                await safe_send_channel(ctx.channel, f"❌ `{currency}` was specified more than once.")
                return None
            try:
                amount = int(raw_amount)
            except ValueError:
                await safe_send_channel(ctx.channel, f"❌ `{raw_amount}` is not a valid amount.")
                return None
            deltas[field] = amount
        return deltas

    @commands.command(name="balance")
    @commands.has_role("Leaderteam")
    async def show_balance(self, ctx, username: str):
        member = await self._resolve_member(ctx, username)
        if not member:
            return

        await safe_send_channel(
            ctx.channel,
            f"📒 **{member.get('username', username)}**\n"
            f"💎 Gems: `{member.get('balance_gems', 0)}`\n"
            f"💰 Gold: `{member.get('balance_gold', 0)}`"
        )

    @commands.command(name="editbalance")
    @commands.has_role("Leaderteam")
    async def edit_balance(self, ctx, username: str, *changes: str):
        deltas = await self._parse_changes(
            ctx, changes,
            "❌ Usage: `editbalance <wov_username> <gems|gold> <amount> [<gems|gold> <amount> ...]`"
        )
        if deltas is None:
            return

        if all(amount == 0 for amount in deltas.values()):
            await safe_send_channel(ctx.channel, "❌ Amounts can't all be zero.")
            return

        member = await self._resolve_member(ctx, username)
        if not member:
            return

        members_col.update_one({"_id": member["_id"]}, {"$inc": deltas})

        lines = []
        for field, amount in deltas.items():
            new_balance = member.get(field, 0) + amount
            emoji = "💎" if field == "balance_gems" else "💰"
            lines.append(f"{emoji} `{amount:+}` → `{new_balance}`")

        log_event(
            f"Edited {member.get('username')}: "
            + ", ".join(f"{field} {amount:+}" for field, amount in deltas.items()),
            "success"
        )
        await safe_send_channel(
            ctx.channel,
            f"✅ Updated **{member.get('username', username)}**:\n" + "\n".join(lines)
        )

    @commands.command(name="transferbalance")
    @commands.has_role("Leaderteam")
    async def transfer_balance(self, ctx, from_username: str, to_username: str, *changes: str):
        deltas = await self._parse_changes(
            ctx, changes,
            "❌ Usage: `transferbalance <from> <to> <gems|gold> <amount> [<gems|gold> <amount> ...]`"
        )
        if deltas is None:
            return

        if any(amount <= 0 for amount in deltas.values()):
            await safe_send_channel(ctx.channel, "❌ Transfer amounts must be positive.")
            return

        sender = await self._resolve_member(ctx, from_username)
        if not sender:
            return
        recipient = await self._resolve_member(ctx, to_username)
        if not recipient:
            return

        if sender["_id"] == recipient["_id"]:
            await safe_send_channel(ctx.channel, "❌ Sender and recipient can't be the same account.")
            return

        members_col.update_one({"_id": sender["_id"]}, {"$inc": {field: -amount for field, amount in deltas.items()}})
        members_col.update_one({"_id": recipient["_id"]}, {"$inc": deltas})

        lines = []
        for field, amount in deltas.items():
            emoji = "💎" if field == "balance_gems" else "💰"
            lines.append(f"{emoji} `{amount}`")

        log_event(
            f"Transferred from {sender.get('username')} to {recipient.get('username')}: "
            + ", ".join(f"{field} {amount}" for field, amount in deltas.items()),
            "success"
        )
        await safe_send_channel(
            ctx.channel,
            f"✅ Transferred from **{sender.get('username', from_username)}** "
            f"to **{recipient.get('username', to_username)}**:\n" + "\n".join(lines)
        )


async def setup(bot):
    await bot.add_cog(Accounts(bot))
