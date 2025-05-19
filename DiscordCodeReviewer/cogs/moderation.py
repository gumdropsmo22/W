import asyncio
import logging
import sqlite3
import traceback
from pathlib import Path
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from typing import Optional, Union
from dateutil.parser import isoparse
from cogs import CovenTools
from coven_ai import generate_wilhelmina_reply
from config import MOD_LOG_CHANNEL_ID

# Initialize logging
log = logging.getLogger(__name__)

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._mute_role_name = "Muted"
        self._warn_logs = {}  # {guild_id: {user_id: [warns]}}
        self._db_path = Path("data/moderation.db")
        self._db_path.parent.mkdir(exist_ok=True)
        self._ai_cooldowns = {}  # Track AI response cooldowns

        # Initialize database
        asyncio.create_task(self._init_db())
        asyncio.create_task(self.load_warns())

    async def _init_db(self):
        """Initialize the SQLite database"""
        async with asyncio.Lock():
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            # Create tables if they don't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS warns (
                    guild_id INTEGER,
                    user_id INTEGER,
                    moderator_id INTEGER,
                    reason TEXT,
                    timestamp TEXT,
                    PRIMARY KEY (guild_id, user_id, timestamp)
                )
            """)

            conn.commit()
            conn.close()


    async def _log_error(self, error: str):
        if MOD_LOG_CHANNEL_ID:
            channel = self.bot.get_channel(MOD_LOG_CHANNEL_ID)
            if channel:
                embed = discord.Embed(
                    title="⚠️ Moderation Error",
                    description=f"```{error[:1000]}```",
                    color=0xFF0000,
                    timestamp=datetime.utcnow()
                )
                await channel.send(embed=embed)

    async def _generate_sassy_response(self, ctx, action, target, reason=None):
        now = discord.utils.utcnow().timestamp()
        if now - self._ai_cooldowns.get(ctx.guild.id, 0) < 60:
            return ""
        self._ai_cooldowns[ctx.guild.id] = now
        prompt = f"{ctx.author.display_name} {action} {target.display_name} for: {reason or 'no reason'}. Sass it."
        try:
            return await generate_wilhelmina_reply(prompt)
        except Exception:
            await self._log_error(f"AI failed: {traceback.format_exc()}")
            return ""


    async def save_warns(self):
        """Save warnings to database"""
        async with asyncio.Lock():
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            # Clear existing data
            cursor.execute("DELETE FROM warns")

            # Insert current warnings
            for guild_id, users in self._warn_logs.items():
                for user_id, warns in users.items():
                    for warn in warns:
                        cursor.execute(
                            "INSERT INTO warns VALUES (?, ?, ?, ?, ?)",
                            (
                                guild_id,
                                user_id,
                                warn["moderator"],
                                warn["reason"],
                                warn["timestamp"]
                            )
                        )

            conn.commit()
            conn.close()

    async def load_warns(self):
        """Load warnings from database"""
        async with asyncio.Lock():
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM warns")
            rows = cursor.fetchall()
            conn.close()

            self._warn_logs = {}
            for row in rows:
                guild_id, user_id, moderator_id, reason, timestamp = row
                guild_warns = self._warn_logs.setdefault(guild_id, {})
                user_warns = guild_warns.setdefault(user_id, [])
                user_warns.append({
                    "moderator": moderator_id,
                    "reason": reason,
                    "timestamp": timestamp
                })

    async def _get_mute_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        """Get or create mute role with proper permissions"""
        if not guild.me.guild_permissions.manage_roles:
            return None

        mute_role = discord.utils.get(guild.roles, name=self._mute_role_name)

        if not mute_role:
            try:
                mute_role = await guild.create_role(
                    name=self._mute_role_name,
                    color=discord.Color.dark_gray(),
                    reason="Automatic mute role creation"
                )

                # Apply mute permissions to all channels
                for channel in guild.channels:
                    try:
                        await channel.set_permissions(
                            mute_role,
                            send_messages=False,
                            speak=False,
                            add_reactions=False,
                            create_public_threads=False,
                            create_private_threads=False,
                            send_messages_in_threads=False
                        )
                    except discord.Forbidden:
                        continue
            except discord.Forbidden:
                log.error(f"Missing permissions to create mute role in {guild.name}")
                return None

        return mute_role

    @commands.hybrid_command()
    @app_commands.describe(
        member="Member to warn",
        reason="Reason for warning"
    )
    @CovenTools.is_warlock()
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str):
        """Issue a formal warning to a member"""
        if member == ctx.author:
            return await ctx.send("I admire your self-loathing, but no.", ephemeral=True)
        if member.guild_permissions.administrator:
            return await ctx.send("The coven elders are untouchable.", ephemeral=True)
        if member.top_role >= ctx.author.top_role:
            return await ctx.send(
                "You dare overreach your station? How... ambitious.",
                ephemeral=True
            )

        # Log warning
        guild_warns = self._warn_logs.setdefault(ctx.guild.id, {})
        user_warns = guild_warns.setdefault(member.id, [])
        user_warns.append({
            "moderator": ctx.author.id,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        })

        await self.save_warns()

        # Send DM
        embed = discord.Embed(
            title=f"⚠️ Warning in {ctx.guild.name}",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(
            name="Total Warnings", 
            value=str(len(user_warns)), 
            inline=True
        )
        embed.set_footer(text="Continued violations may result in mute or ban")

        try:
            await member.send(embed=embed)
        except discord.Forbidden:
            pass  # User has DMs disabled

        # Send confirmation
        confirm_embed = discord.Embed(
            title="⚠️ Warning Issued",
            description=f"{member.mention} has been warned",
            color=discord.Color.orange()
        )
        confirm_embed.add_field(name="Reason", value=reason, inline=False)
        confirm_embed.add_field(
            name="Total Warnings", 
            value=str(len(user_warns)), 
            inline=True
        )

        await ctx.send(embed=confirm_embed)

        # Generate sassy response
        sassy_reply = await self._generate_sassy_response(ctx, "warned", member, reason)
        if sassy_reply:
            await ctx.send(f"🔮 *Wilhelmina cackles:* {sassy_reply}")

    @commands.hybrid_command()
    @app_commands.describe(
        member="Member to mute",
        duration="Mute duration (e.g. 1h, 30m)",
        reason="Reason for mute"
    )
    @CovenTools.is_warlock()
    async def mute(self, ctx: commands.Context, 
                 member: discord.Member,
                 duration: Optional[str] = None,
                 *, reason: Optional[str] = None):
        """Mute a member with optional duration"""
        # Permission and hierarchy checks
        if member == ctx.author:
            return await ctx.send("You can't mute yourself!", ephemeral=True)
        if member.guild_permissions.administrator:
            return await ctx.send("Can't mute administrators!", ephemeral=True)
        if member.top_role >= ctx.author.top_role:
            return await ctx.send(
                "You can't mute someone with equal/higher rank!",
                ephemeral=True
            )

        mute_role = await self._get_mute_role(ctx.guild)
        if not mute_role:
            return await ctx.send(
                "I don't have permission to manage roles!",
                ephemeral=True
            )

        if mute_role in member.roles:
            return await ctx.send("Member is already muted!", ephemeral=True)

        # Parse duration
        mute_time = None
        if duration:
            try:
                time_units = {
                    's': 'seconds',
                    'm': 'minutes',
                    'h': 'hours',
                    'd': 'days'
                }
                unit = duration[-1].lower()
                amount = int(duration[:-1])
                mute_time = timedelta(**{time_units[unit]: amount})
            except (ValueError, IndexError, KeyError):
                return await ctx.send(
                    "Invalid duration format! Use like `1h`, `30m`, `2d`",
                    ephemeral=True
                )

        # Apply mute
        try:
            await member.add_roles(mute_role, reason=reason)
            log.info(f"{ctx.author} muted {member} for {reason}")
        except discord.Forbidden:
            return await ctx.send("Failed to mute member!", ephemeral=True)

        # Create embed
        embed = discord.Embed(
            title="🔇 Member Muted",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="User", value=member.mention, inline=True)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        if mute_time:
            embed.add_field(
                name="Duration", 
                value=str(mute_time).replace("days", "d").replace("day", "d"),
                inline=False
            )

        await ctx.send(embed=embed)

        # Generate sassy response
        sassy_reply = await self._generate_sassy_response(ctx, "muted", member, reason)
        if sassy_reply:
            await ctx.send(f"🔮 *Wilhelmina observes:* {sassy_reply}")

        # Schedule unmute if duration provided
        if mute_time:
            await self._schedule_unmute(member, mute_time, ctx.author, reason)

    async def _schedule_unmute(self, member: discord.Member, 
                             duration: timedelta,
                             moderator: discord.Member,
                             reason: Optional[str] = None):
        """Schedule automatic unmute after duration"""
        await asyncio.sleep(duration.total_seconds())

        # Check if member still exists and is muted
        guild = self.bot.get_guild(member.guild.id)
        if not guild:
            return

        member = guild.get_member(member.id)
        if not member:
            return

        mute_role = discord.utils.get(guild.roles, name=self._mute_role_name)
        if not mute_role or mute_role not in member.roles:
            return

        # Unmute
        try:
            await member.remove_roles(mute_role, reason="Automatic unmute after timeout")

            # Log in mod channel
            if MOD_LOG_CHANNEL_ID:
                channel = self.bot.get_channel(MOD_LOG_CHANNEL_ID)
                if channel:
                    embed = discord.Embed(
                        title="🔊 Member Automatically Unmuted",
                        color=discord.Color.green(),
                        timestamp=datetime.utcnow()
                    )
                    embed.add_field(name="User", value=member.mention, inline=True)
                    embed.add_field(name="Original Mute By", value=moderator.mention, inline=True)
                    if reason:
                        embed.add_field(name="Original Reason", value=reason, inline=False)

                    await channel.send(embed=embed)

            # DM the user
            try:
                await member.send(f"Your mute in **{guild.name}** has expired.")
            except discord.Forbidden:
                pass

        except discord.Forbidden:
            log.error(f"Failed to unmute {member} (ID: {member.id}) in {guild.name}")
        except Exception as e:
            log.error(f"Error unmuting {member}: {e}")
            await self._log_error(f"Error during scheduled unmute: {traceback.format_exc()}")

    @commands.hybrid_command()
    @app_commands.describe(
        member="Member to unmute",
        reason="Reason for unmute"
    )
    @CovenTools.is_warlock()
    async def unmute(self, ctx: commands.Context, member: discord.Member, *, reason: Optional[str] = None):
        """Unmute a previously muted member"""
        mute_role = discord.utils.get(ctx.guild.roles, name=self._mute_role_name)

        if not mute_role:
            return await ctx.send("No mute role found!", ephemeral=True)

        if mute_role not in member.roles:
            return await ctx.send("This member is not muted!", ephemeral=True)

        try:
            await member.remove_roles(mute_role, reason=reason or "Manual unmute")

            embed = discord.Embed(
                title="🔊 Member Unmuted",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=member.mention, inline=True)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            if reason:
                embed.add_field(name="Reason", value=reason, inline=False)

            await ctx.send(embed=embed)

            # Generate sassy response
            sassy_reply = await self._generate_sassy_response(ctx, "unmuted", member, reason)
            if sassy_reply:
                await ctx.send(f"🔮 *Wilhelmina notes:* {sassy_reply}")

        except discord.Forbidden:
            await ctx.send("I don't have permission to manage roles!", ephemeral=True)
        except Exception as e:
            await ctx.send(f"Error: {str(e)}", ephemeral=True)
            await self._log_error(f"Unmute error: {traceback.format_exc()}")

    @commands.hybrid_command()
    @app_commands.describe(member="Member to check warnings for")
    async def warnings(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """View warnings for a member"""
        target = member or ctx.author

        # Can only view others' warnings if you're a moderator
        if target != ctx.author and not await CovenTools.is_warlock()(ctx):
            return await ctx.send("You can only view your own warnings!", ephemeral=True)

        guild_warns = self._warn_logs.get(ctx.guild.id, {})
        user_warns = guild_warns.get(target.id, [])

        if not user_warns:
            return await ctx.send(
                f"{target.display_name} has a clean slate... for now.",
                ephemeral=(target != ctx.author)
            )

        embed = discord.Embed(
            title=f"⚠️ Warnings for {target.display_name}",
            color=discord.Color.orange(),
            description=f"Total: **{len(user_warns)}** warning(s)"
        )

        # Sort by most recent first
        sorted_warns = sorted(
            user_warns,
            key=lambda w: isoparse(w["timestamp"]),
            reverse=True
        )

        for i, warn in enumerate(sorted_warns[:10], 1):
            moderator = ctx.guild.get_member(warn["moderator"])
            mod_name = moderator.display_name if moderator else "Unknown"

            warn_time = isoparse(warn["timestamp"]).strftime("%Y-%m-%d %H:%M")

            embed.add_field(
                name=f"Warning #{i} - {warn_time}",
                value=f"**Reason:** {warn['reason']}\n**By:** {mod_name}",
                inline=False
            )

        if len(sorted_warns) > 10:
            embed.set_footer(text=f"Showing 10 of {len(sorted_warns)} warnings")

        await ctx.send(embed=embed, ephemeral=(target != ctx.author))

    @commands.hybrid_command()
    @app_commands.describe(
        member="Member to clear warnings for",
        amount="Number of warnings to clear (all if not specified)"
    )
    @CovenTools.is_warlock()
    async def clearwarnings(self, ctx: commands.Context, member: discord.Member, amount: Optional[int] = None):
        """Clear warnings for a member"""
        guild_warns = self._warn_logs.get(ctx.guild.id, {})
        user_warns = guild_warns.get(member.id, [])

        if not user_warns:
            return await ctx.send(f"{member.display_name} has no warnings to clear.", ephemeral=True)

        if amount is None or amount >= len(user_warns):
            # Clear all warnings
            del guild_warns[member.id]
            cleared = len(user_warns)
        else:
            # Clear specific number (most recent first)
            sorted_warns = sorted(
                user_warns,
                key=lambda w: isoparse(w["timestamp"]),
                reverse=True
            )[amount:]

            if not sorted_warns:
                del guild_warns[member.id]
            else:
                guild_warns[member.id] = sorted_warns

            cleared = len(user_warns) - len(sorted_warns)

        await self.save_warns()

        embed = discord.Embed(
            title="🧹 Warnings Cleared",
            description=f"Cleared **{cleared}** warning(s) for {member.mention}",
            color=discord.Color.green()
        )

        await ctx.send(embed=embed)

        # Generate sassy response
        prompt = (
            f"{ctx.author.display_name} just cleared {cleared} warnings for {member.display_name}. "
            "Make a witchy comment about washing away sins or darkness."
        )
        try:
            reply = await generate_wilhelmina_reply(prompt)
            await ctx.send(f"🔮 *Wilhelmina muses:* {reply}")
        except Exception as e:
            log.error(f"Failed to generate response: {e}")

async def setup(bot):
    await bot.add_cog(Moderation(bot))
