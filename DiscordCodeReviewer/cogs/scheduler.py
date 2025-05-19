from discord import app_commands
import asyncio
import discord
import logging
import sqlite3
from datetime import datetime, timedelta
from discord.ext import commands, tasks
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from .. import CovenTools

# Initialize logging
log = logging.getLogger(__name__)

class Scheduler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._db_path = Path("data/scheduler.db")
        self._db_path.parent.mkdir(exist_ok=True)
        self._tasks = {}  # {event_id: asyncio.Task}
        self._reminders = {}  # {user_id: {reminder_id: asyncio.Task}}

        # Initialize database
        asyncio.create_task(self._init_db())
        # Start the scheduled events checker
        self.check_events.start()

    async def _init_db(self):
        """Initialize the SQLite database"""
        async with asyncio.Lock():
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            # Create tables if they don't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    creator_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    event_time TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    reminder_sent BOOLEAN DEFAULT 0
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    remind_time TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            conn.commit()
            conn.close()

    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.check_events.cancel()

        # Cancel all running tasks
        for task in self._tasks.values():
            task.cancel()

        for user_reminders in self._reminders.values():
            for task in user_reminders.values():
                task.cancel()

    @tasks.loop(minutes=5)
    async def check_events(self):
        """Check for events that need reminders"""
        now = datetime.utcnow()
        reminder_threshold = now + timedelta(minutes=30)

        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        # Get events that need reminders
        cursor.execute("""
            SELECT id, guild_id, channel_id, title, event_time
            FROM scheduled_events
            WHERE event_time <= ? AND event_time > ? AND reminder_sent = 0
        """, (reminder_threshold.isoformat(), now.isoformat()))

        events = cursor.fetchall()

        for event_id, guild_id, channel_id, title, event_time in events:
            # Schedule reminders
            self._schedule_event_reminder(
                event_id, guild_id, channel_id, title, 
                datetime.fromisoformat(event_time)
            )

            # Mark as reminded
            cursor.execute(
                "UPDATE scheduled_events SET reminder_sent = 1 WHERE id = ?",
                (event_id,)
            )

        # Clean up old events
        cursor.execute(
            "DELETE FROM scheduled_events WHERE event_time < ?",
            ((now - timedelta(days=1)).isoformat(),)
        )

        conn.commit()
        conn.close()

    @check_events.before_loop
    async def before_check_events(self):
        """Wait until the bot is ready before starting the task"""
        await self.bot.wait_until_ready()

    def _schedule_event_reminder(self, event_id, guild_id, channel_id, title, event_time):
        """Schedule a reminder for an event"""
        async def _send_reminder():
            # Calculate time until event
            now = datetime.utcnow()
            time_until = event_time - now
            minutes_until = int(time_until.total_seconds() / 60)

            # Get guild and channel
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return

            channel = guild.get_channel(channel_id)
            if not channel:
                return

            # Send reminder
            embed = discord.Embed(
                title="🔮 Event Reminder",
                description=f"**{title}** will begin in {minutes_until} minutes!",
                color=0x9B59B6
            )

            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                log.error(f"Cannot send reminder in channel {channel_id} (no permissions)")
            except Exception as e:
                log.error(f"Error sending event reminder: {e}")

        # Calculate when to send the reminder
        now = datetime.utcnow()
        time_until_reminder = event_time - now - timedelta(minutes=30)

        # If it's less than 30 minutes until event, send immediately
        if time_until_reminder.total_seconds() <= 0:
            self._tasks[event_id] = asyncio.create_task(_send_reminder())
        else:
            # Schedule for 30 minutes before
            self._tasks[event_id] = asyncio.create_task(
                self._delayed_reminder(
                    time_until_reminder.total_seconds(),
                    _send_reminder
                )
            )

    @staticmethod
    async def _delayed_reminder(delay, callback):
        """Helper function to delay a reminder"""
        await asyncio.sleep(delay)
        await callback()

    @commands.hybrid_command()
    @app_commands.describe(
        title="Event title",
        date="Date in YYYY-MM-DD format",
        time="Time in HH:MM format (24-hour)",
        description="Optional event description"
    )
    async def schedule(self, ctx, title: str, date: str, time: str, *, description: str = None):
        """Schedule a coven event with reminders"""
        # Validate date and time format
        try:
            event_date = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        except ValueError:
            return await ctx.send(
                "🕰️ Invalid date or time format! Use YYYY-MM-DD and HH:MM (24-hour time).",
                ephemeral=True
            )

        # Check if event is in the future
        if event_date <= datetime.utcnow():
            return await ctx.send(
                "⏳ You can't schedule events in the past, even with time magic!",
                ephemeral=True
            )

        # Store in database
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO scheduled_events 
            (guild_id, channel_id, creator_id, title, description, event_time, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ctx.guild.id,
                ctx.channel.id,
                ctx.author.id,
                title,
                description,
                event_date.isoformat(),
                datetime.utcnow().isoformat()
            )
        )

        event_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Create embed
        embed = discord.Embed(
            title=f"📅 Event Scheduled: {title}",
            color=0x9B59B6,
            timestamp=event_date
        )
        embed.add_field(name="Date & Time", value=event_date.strftime("%A, %B %d at %I:%M %p"), inline=False)
        if description:
            embed.add_field(name="Description", value=description, inline=False)
        embed.add_field(name="Organizer", value=ctx.author.mention, inline=True)
        embed.add_field(name="Channel", value=ctx.channel.mention, inline=True)
        embed.set_footer(text=f"Event ID: {event_id} • Reminders will be sent 30 minutes before")

        await ctx.send(embed=embed)

        # If event is within 30 minutes, schedule reminder now
        time_until_event = event_date - datetime.utcnow()
        if time_until_event <= timedelta(minutes=30):
            self._schedule_event_reminder(
                event_id, ctx.guild.id, ctx.channel.id, title, event_date
            )

    @commands.hybrid_command()
    async def events(self, ctx):
        """List upcoming coven events"""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        # Get upcoming events for this guild
        cursor.execute(
            """
            SELECT id, channel_id, creator_id, title, description, event_time
            FROM scheduled_events
            WHERE guild_id = ? AND event_time > ?
            ORDER BY event_time ASC
            """,
            (ctx.guild.id, datetime.utcnow().isoformat())
        )

        events = cursor.fetchall()
        conn.close()

        if not events:
            return await ctx.send("📅 No upcoming events scheduled in the coven.", ephemeral=True)

        # Create events list embed
        embed = discord.Embed(
            title="📅 Upcoming Coven Events",
            color=0x9B59B6,
            description=f"Found {len(events)} upcoming event(s)"
        )

        for event_id, channel_id, creator_id, title, description, event_time in events:
            event_datetime = datetime.fromisoformat(event_time)
            time_until = event_datetime - datetime.utcnow()
            days, remainder = divmod(time_until.total_seconds(), 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, _ = divmod(remainder, 60)

            time_str = []
            if days > 0:
                time_str.append(f"{int(days)}d")
            if hours > 0 or days > 0:  # Show hours if there are any, or if we already showed days
                time_str.append(f"{int(hours)}h")
            time_str.append(f"{int(minutes)}m")

            # Get channel mention
            channel = self.bot.get_channel(channel_id)
            channel_mention = channel.mention if channel else "Unknown Channel"

            # Add field for each event
            embed.add_field(
                name=f"📌 {title} (in {' '.join(time_str)})",
                value=(
                    f"**When:** <t:{int(event_datetime.timestamp())}:F>\n"
                    f"**Where:** {channel_mention}\n"
                    f"**Description:** {description[:150]}{'...' if len(description) > 150 else ''}"
                ),
                inline=False
            )
        embed = discord.Embed(
            title="📅 Upcoming Coven Events",
            color=0x9B59B6,
            description=f"Found {len(events)} upcoming event(s)"
        )

        for event_id, channel_id, creator_id, title, description, event_time in events:
            event_datetime = datetime.fromisoformat(event_time)
            time_until = event_datetime - datetime.utcnow()
            days, remainder = divmod(time_until.total_seconds(), 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, _ = divmod(remainder, 60)

            relative_time = []
            if days > 0:
                relative_time.append(f"{int(days)} day{'s' if days != 1 else ''}")
            if hours > 0:
                relative_time.append(f"{int(hours)} hour{'s' if hours != 1 else ''}")
            if minutes > 0 and days == 0:
                relative_time.append(f"{int(minutes)} minute{'s' if minutes != 1 else ''}")

            time_display = ", ".join(relative_time) if relative_time else "Very soon!"

            creator = ctx.guild.get_member(creator_id)
            creator_name = creator.display_name if creator else "Unknown Witch"

            channel = ctx.guild.get_channel(channel_id)
            channel_name = channel.mention if channel else "Unknown Channel"

            embed.add_field(
                name=f"{title} (in {time_display})",
                value=(
                    f"🕰️ {event_datetime.strftime('%A, %B %d at %I:%M %p')}\n"
                    f"📌 {channel_name}\n"
                    f"👤 Organized by {creator_name}\n"
                    f"🔍 ID: {event_id}"
                ),
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.hybrid_command()
    @app_commands.describe(event_id="ID of the event to cancel")
    @CovenTools.is_warlock()
    async def cancelevent(self, ctx, event_id: int):
        """Cancel a scheduled event (Warlocks only)"""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        # Check if event exists and belongs to this guild
        cursor.execute(
            "SELECT title, creator_id FROM scheduled_events WHERE id = ? AND guild_id = ?",
            (event_id, ctx.guild.id)
        )

        result = cursor.fetchone()
        if not result:
            conn.close()
            return await ctx.send("🔍 Event not found! Check the ID and try again.", ephemeral=True)

        title, creator_id = result

        # Delete the event
        cursor.execute("DELETE FROM scheduled_events WHERE id = ?", (event_id,))
        conn.commit()
        conn.close()

        # Cancel any running task
        if event_id in self._tasks:
            self._tasks[event_id].cancel()
            del self._tasks[event_id]

        # Notify
        embed = discord.Embed(
            title="🚫 Event Cancelled",
            description=f"The event **{title}** has been cancelled by {ctx.author.mention}",
            color=0xFF5733
        )

        creator = ctx.guild.get_member(creator_id)
        if creator:
            embed.add_field(name="Original Organizer", value=creator.mention, inline=True)

            # Try to DM the creator
            try:
                await creator.send(
                    f"Your scheduled event **{title}** in {ctx.guild.name} has been cancelled by {ctx.author.display_name}."
                )
            except discord.Forbidden:
                pass  # Can't DM user

        await ctx.send(embed=embed)

    @commands.hybrid_command()
    @app_commands.describe(
        reminder="What to remind you about",
        time="When to remind you (e.g. 30m, 2h, 1d)"
    )
    async def remind(self, ctx, time: str, *, reminder: str):
        """Set a personal reminder"""
        # Parse time
        try:
            duration = self._parse_time(time)
            if not duration:
                return await ctx.send(
                    "⏰ Invalid time format! Use like `30m`, `2h`, `1d`.",
                    ephemeral=True
                )

            if duration > timedelta(days=30):
                return await ctx.send(
                    "⏰ Reminders can only be set for up to 30 days in the future.",
                    ephemeral=True
                )
        except ValueError:
            return await ctx.send(
                "⏰ Invalid time format! Use like `30m`, `2h`, `1d`.",
                ephemeral=True
            )

        # Calculate reminder time
        now = datetime.utcnow()
        remind_time = now + duration

        # Store in database
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO reminders
            (user_id, channel_id, content, remind_time, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                ctx.author.id,
                ctx.channel.id,
                reminder,
                remind_time.isoformat(),
                now.isoformat()
            )
        )

        reminder_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Schedule reminder
        user_reminders = self._reminders.setdefault(ctx.author.id, {})
        user_reminders[reminder_id] = asyncio.create_task(
            self._send_reminder(ctx.author.id, ctx.channel.id, reminder_id, reminder, duration.total_seconds())
        )

        # Confirmation message
        time_str = self._format_timedelta(duration)
        await ctx.send(
            f"⏰ I'll remind you about **{reminder}** in {time_str}.",
            ephemeral=True
        )

    async def _send_reminder(self, user_id, channel_id, reminder_id, content, delay):
        """Send a reminder after the specified delay"""
        await asyncio.sleep(delay)

        # Get user and channel
        user = self.bot.get_user(user_id)
        if not user:
            return

        channel = self.bot.get_channel(channel_id)

        # Create embed
        embed = discord.Embed(
            title="⏰ Reminder",
            description=content,
            color=0x9B59B6,
            timestamp=datetime.utcnow()
        )

        # Try to DM the user first
        try:
            await user.send(embed=embed)
            sent_dm = True
        except discord.Forbidden:
            sent_dm = False

        # If in a channel and we couldn't DM, send there instead
        if channel and not sent_dm:
            try:
                await channel.send(f"{user.mention} ⏰ **Reminder:**", embed=embed)
            except discord.Forbidden:
                log.error(f"Cannot send reminder in channel {channel_id} (no permissions)")

        # Remove from database
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        conn.commit()
        conn.close()

        # Remove from active reminders
        if user_id in self._reminders and reminder_id in self._reminders[user_id]:
            del self._reminders[user_id][reminder_id]

    @commands.hybrid_command()
    async def reminders(self, ctx):
        """List your active reminders"""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        # Get user's reminders
        cursor.execute(
            """
            SELECT id, content, remind_time
            FROM reminders
            WHERE user_id = ?
            ORDER BY remind_time ASC
            """,
            (ctx.author.id,)
        )

        reminders = cursor.fetchall()
        conn.close()

        if not reminders:
            return await ctx.send("⏰ You have no active reminders.", ephemeral=True)

        # Create list embed
        embed = discord.Embed(
            title="⏰ Your Active Reminders",
            color=0x9B59B6,
            description=f"You have {len(reminders)} active reminder(s)"
        )

        now = datetime.utcnow()
        for reminder_id, content, remind_time in reminders:
            remind_datetime = datetime.fromisoformat(remind_time)
            time_left = remind_datetime - now

            embed.add_field(
                name=f"Reminder #{reminder_id} (in {self._format_timedelta(time_left)})",
                value=f"```{content}```",
                inline=False
            )

        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command()
    @app_commands.describe(reminder_id="ID of the reminder to cancel")
    async def cancelreminder(self, ctx, reminder_id: int):
        """Cancel an active reminder"""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        # Check if reminder exists and belongs to user
        cursor.execute(
            "SELECT content FROM reminders WHERE id = ? AND user_id = ?",
            (reminder_id, ctx.author.id)
        )

        result = cursor.fetchone()
        if not result:
            conn.close()
            return await ctx.send("⏰ Reminder not found! Check the ID and try again.", ephemeral=True)

        content = result[0]

        # Delete the reminder
        cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        conn.commit()
        conn.close()

        # Cancel any running task
        if ctx.author.id in self._reminders and reminder_id in self._reminders[ctx.author.id]:
            self._reminders[ctx.author.id][reminder_id].cancel()
            del self._reminders[ctx.author.id][reminder_id]

        await ctx.send(f"⏰ Reminder cancelled: **{content}**", ephemeral=True)

    @staticmethod
    def _parse_time(time_str: str) -> Optional[timedelta]:
        """Parse a time string like 30m, 2h, 1d into a timedelta"""
        if not time_str or len(time_str) < 2:
            return None

        # Check format is a number followed by a unit
        amount = ""
        unit = time_str[-1].lower()

        for char in time_str[:-1]:
            if char.isdigit():
                amount += char
            else:
                return None

        if not amount:
            return None

        amount = int(amount)

        # Convert to timedelta
        if unit == "s":
            return timedelta(seconds=amount)
        if unit == "m":
            return timedelta(minutes=amount)
        if unit == "h":
            return timedelta(hours=amount)
        if unit == "d":
            return timedelta(days=amount)
        return None

    @staticmethod
    def _format_timedelta(delta: timedelta) -> str:
        """Format a timedelta into a readable string"""
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return f"{seconds} second{'s' if seconds != 1 else ''}"

        minutes, seconds = divmod(seconds, 60)
        if minutes < 60:
            return f"{minutes} minute{'s' if minutes != 1 else ''}"

        hours, minutes = divmod(minutes, 60)
        if hours < 24:
            return f"{hours} hour{'s' if hours != 1 else ''} and {minutes} minute{'s' if minutes != 1 else ''}"

        days, hours = divmod(hours, 24)
        return f"{days} day{'s' if days != 1 else ''} and {hours} hour{'s' if hours != 1 else ''}"

async def setup(bot):
    await bot.add_cog(Scheduler(bot))
