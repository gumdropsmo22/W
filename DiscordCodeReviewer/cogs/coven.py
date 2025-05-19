import discord
from discord.ext import commands, tasks
from datetime import datetime, time
from typing import Dict, Any
from config import (
    AUTO_ROLE_ID,
    TEA_CHANNEL_ID
)

# Global access to user data for permission checks
_user_data = {}

def get_user_data(user_id: int) -> Dict[str, Any]:
    """Return user data for whisper checks"""
    return _user_data.get(user_id, {"whispers": 0, "last_daily": None})

class Coven(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_data: Dict[int, Dict[str, Any]] = _user_data  # Link to global
        self.role_map = {
            0: {"name": "🕯️ Neophyte", "id": AUTO_ROLE_ID},
            50: {"name": "🔮 Seer", "color": 0x800080},
            150: {"name": "🕵️‍♀️ Shadow Inquisitor", "color": 0x00008B},
            300: {"name": "👑 High Priestess", "color": 0xFFD700},
            500: {"name": "👑 High Priest", "color": 0xFFD700}
        }
        self.daily_reset.start()

    def get_tier(self, user_id: int) -> int:
        """Returns the highest tier a user qualifies for based on whispers"""
        whispers = self.user_data.get(user_id, {}).get("whispers", 0)
        return max((t for t in self.role_map if t <= whispers), default=0)

    @tasks.loop(time=time(hour=0))  # Midnight UTC
    async def daily_reset(self):
        """Reset daily counters and process tier promotions"""
        for user_id, data in self.user_data.items():
            data["last_daily"] = datetime.utcnow()

            # Update roles for active users
            for guild in self.bot.guilds:
                member = guild.get_member(user_id)
                if member:
                    await self._update_roles(member)

        self.bot.dispatch("coven_reset")

    @daily_reset.before_loop
    async def before_daily_reset(self):
        """Wait for bot to be ready before starting task"""
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Track whispers in designated channels"""
        if message.author.bot or not message.guild:
            return

        if message.channel.id == TEA_CHANNEL_ID:
            user_id = message.author.id
            self.user_data.setdefault(user_id, {"whispers": 0, "last_daily": None})
            self.user_data[user_id]["whispers"] += 1

            # Update roles if tier changed
            await self._update_roles(message.author)

    async def _update_roles(self, member: discord.Member):
        """Handle role promotions/demotions"""
        if not member.guild.me.guild_permissions.manage_roles:
            return

        tier = self.get_tier(member.id)
        guild = member.guild

        # Remove all tier roles
        current_tier_roles = [
            role for role in member.roles 
            if any(role.name == r["name"] for r in self.role_map.values())
        ]
        if current_tier_roles:
            await member.remove_roles(*current_tier_roles)

        # Add new tier role (create if missing)
        new_role = discord.utils.get(guild.roles, name=self.role_map[tier]["name"])
        if not new_role:
            try:
                new_role = await guild.create_role(
                    name=self.role_map[tier]["name"],
                    color=discord.Color(self.role_map[tier].get("color", 0x808080)),
                    hoist=True,
                    mentionable=(tier >= 300)  # High Priest/ess can be mentioned
                )

                # Position new role above lower tiers
                positions = {
                    role: idx for idx, role in enumerate(guild.roles) 
                    if role.name in [r["name"] for r in self.role_map.values()]
                }
                if positions:
                    await new_role.edit(position=max(positions.values()) + 1)
            except discord.Forbidden:
                return  # Can't create role

        try:
            await member.add_roles(new_role)
        except discord.Forbidden:
            pass  # Can't add role

    @commands.hybrid_command()
    async def myrank(self, ctx: commands.Context):
        """Display your current coven status"""
        tier = self.get_tier(ctx.author.id)
        whispers = self.user_data.get(ctx.author.id, {}).get("whispers", 0)

        embed = discord.Embed(
            title=f"{ctx.author.display_name}'s Coven Status",
            color=self.role_map[tier].get("color", 0x808080)
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)

        embed.add_field(name="Current Tier", value=self.role_map[tier]["name"], inline=True)
        embed.add_field(name="Whispers", value=f"{whispers}", inline=True)

        # Calculate progress to next tier
        higher_tiers = sorted(t for t in self.role_map if t > tier)
        if higher_tiers:
            next_tier = higher_tiers[0]
            progress = next_tier - whispers
            embed.add_field(
                name="Progress", 
                value=f"{progress} whispers to {self.role_map[next_tier]['name']}",
                inline=False
            )

            # Progress bar visualization
            percentage = min(100, int((whispers - tier) / (next_tier - tier) * 100))
            embed.add_field(
                name="\u200b",
                value=f"`[{('█' * (percentage // 10)).ljust(10)}] {percentage}%`",
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_coven_reset(self):
        """Handle daily maintenance tasks"""

async def setup(bot):
    cog = Coven(bot)
    await bot.add_cog(cog)

    # Store globally for permission checks
    global _user_data
    _user_data = cog.user_data
