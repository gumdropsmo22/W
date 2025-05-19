import asyncio
import logging
import re
from typing import Optional, Union
from collections import deque

import discord
import yt_dlp
from discord import app_commands
from discord.ext import commands

# Suppress noise about console usage from errors
yt_dlp.utils.bug_reports_message = lambda: ''

# Logger setup
log = logging.getLogger(__name__)

# Audio source options
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '127.0.0.1',
    'extract_flat': 'in_playlist',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'opus',
        'preferredquality': '192',
    }],
}

ffmpeg_options = {
    'options': '-vn -b:a 192k',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = self.parse_duration(data.get('duration'))
        self.thumbnail = data.get('thumbnail')
        self.uploader = data.get('uploader')
        self.views = data.get('view_count')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

    @staticmethod
    def parse_duration(duration: int) -> str:
        if not duration:
            return "Live"
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"

class MusicQueue:
    def __init__(self):
        self._queue = deque()
        self._history = deque(maxlen=10)
        self.loop = False
        self.loop_single = False
        self.now_playing = None

    def __len__(self):
        return len(self._queue)

    def add(self, item):
        self._queue.append(item)

    def next(self) -> Optional[dict]:
        if not self._queue:
            return None

        if self.loop_single and self.now_playing:
            return self.now_playing

        self.now_playing = self._queue.popleft()

        if self.loop:
            self._queue.append(self.now_playing.copy())

        self._history.append(self.now_playing.copy())
        return self.now_playing

    def clear(self):
        self._queue.clear()

    def shuffle(self):
        import random
        random.shuffle(self._queue)

    def move_to_front(self, index: int):
        if 0 <= index < len(self._queue):
            item = self._queue[index]
            del self._queue[index]
            self._queue.appendleft(item)

    def remove(self, index: int):
        if 0 <= index < len(self._queue):
            del self._queue[index]

    def get_queue(self) -> list:
        return list(self._queue)

    def get_history(self) -> list:
        return list(self._history)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}  # guild_id: MusicQueue
        self.votes = {}  # guild_id: set(user_ids)

    def get_queue(self, guild_id: int) -> MusicQueue:
        if guild_id not in self.queues:
            self.queues[guild_id] = MusicQueue()
        return self.queues[guild_id]

    @staticmethod
    async def ensure_voice(ctx: commands.Context):
        """Ensure the bot and user are in a voice channel"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("You're not connected to a voice channel!", ephemeral=True)
            return False

        if ctx.voice_client:
            if ctx.voice_client.channel != ctx.author.voice.channel:
                await ctx.send("I'm already in another voice channel!", ephemeral=True)
                return False
        else:
            try:
                await ctx.author.voice.channel.connect()
            except discord.ClientException:
                await ctx.send("Failed to join the voice channel!", ephemeral=True)
                return False

        return True

    async def play_next(self, ctx: commands.Context):
        """Play the next song in the queue"""
        queue = self.get_queue(ctx.guild.id)
        next_song = queue.next()

        if not next_song:
            await ctx.voice_client.disconnect()
            del self.queues[ctx.guild.id]
            return

        try:
            player = await YTDLSource.from_url(next_song['url'], loop=self.bot.loop, stream=True)
            ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop))

            embed = discord.Embed(
                title="🎶 Now Playing",
                description=f"[{player.title}]({player.url})",
                color=discord.Color.blurple()
            )
            embed.add_field(name="Duration", value=player.duration, inline=True)
            embed.add_field(name="Uploader", value=player.uploader, inline=True)
            embed.add_field(name="Views", value=f"{player.views:,}", inline=True)
            embed.set_thumbnail(url=player.thumbnail)
            embed.set_footer(text=f"Requested by {next_song['requester']}")

            channel = self.bot.get_channel(ctx.channel.id)
            if channel:
                await channel.send(embed=embed)
        except Exception as e:
            log.error(f"Error playing song: {e}")
            channel = self.bot.get_channel(ctx.channel.id)
            if channel:
                await channel.send("Error playing song, skipping...")
            await self.play_next(ctx)

    @commands.hybrid_command(aliases=['p'])
    @app_commands.describe(query="Song name or URL to play")
    async def play(self, ctx: commands.Context, *, query: str):
        """Play a song from YouTube"""
        if not await self.ensure_voice(ctx):
            return

        async with ctx.typing():
            # Check if it's a URL
            url_pattern = re.compile(
                r'^(https?://)?(www\.)?(youtube\.com|youtu\.?be)/.+$'
            )
            is_url = url_pattern.match(query)

            if not is_url and not query.startswith('ytsearch:'):
                query = f'ytsearch:{query}'

            try:
                player = await YTDLSource.from_url(query, loop=self.bot.loop, stream=True)

                song = {
                    'url': player.url,
                    'title': player.title,
                    'duration': player.duration,
                    'thumbnail': player.thumbnail,
                    'uploader': player.uploader,
                    'views': player.views,
                    'requester': ctx.author.display_name
                }

                queue = self.get_queue(ctx.guild.id)
                queue.add(song)

                if not ctx.voice_client.is_playing():
                    await self.play_next(ctx)
                else:
                    embed = discord.Embed(
                        title="🎵 Added to Queue",
                        description=f"[{song['title']}]({song['url']})",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="Position", value=f"{len(queue)}", inline=True)
                    embed.add_field(name="Duration", value=song['duration'], inline=True)
                    embed.set_thumbnail(url=song['thumbnail'])
                    embed.set_footer(text=f"Requested by {ctx.author.display_name}")
                    await ctx.send(embed=embed)
            except Exception as e:
                log.error(f"Error processing song: {e}")
                await ctx.send("Error processing your request. Please try again.")

    @commands.hybrid_command()
    async def skip(self, ctx: commands.Context):
        """Skip the current song"""
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send("Nothing is playing right now!", ephemeral=True)

        # Check if user has permission to force skip
        if ctx.author.guild_permissions.manage_channels:
            ctx.voice_client.stop()
            return await ctx.send("⏭️ Song skipped by moderator.")

        # Vote skip system
        voters = self.votes.setdefault(ctx.guild.id, set())
        required = len(ctx.author.voice.channel.members) // 2

        if ctx.author.id in voters:
            return await ctx.send("You've already voted to skip!", ephemeral=True)

        voters.add(ctx.author.id)
        current = len(voters)

        if current >= required:
            ctx.voice_client.stop()
            await ctx.send("⏭️ Vote passed! Skipping song...")
            self.votes.pop(ctx.guild.id, None)
        else:
            await ctx.send(f"🗳️ Skip vote: {current}/{required} votes")

    @commands.hybrid_command()
    async def stop(self, ctx: commands.Context):
        """Stop playback and clear the queue"""
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send("Nothing is playing right now!", ephemeral=True)

        if not ctx.author.guild_permissions.manage_channels:
            return await ctx.send(
                "You need manage channels permission to stop music!",
                ephemeral=True
            )

        self.get_queue(ctx.guild.id).clear()
        ctx.voice_client.stop()
        await ctx.send("⏹️ Stopped playback and cleared the queue.")

    @commands.hybrid_command(aliases=['q'])
    async def queue(self, ctx: commands.Context):
        """Show the current queue"""
        queue = self.get_queue(ctx.guild.id)

        if not queue.now_playing and len(queue) == 0:
            return await ctx.send("The queue is empty!", ephemeral=True)

        embed = discord.Embed(title="🎼 Music Queue", color=discord.Color.blurple())

        if queue.now_playing:
            embed.add_field(
                name="Now Playing",
                value=f"[{queue.now_playing['title']}]({queue.now_playing['url']})",
                inline=False
            )

        if len(queue) > 0:
            queue_list = "\n".join(
                f"{i+1}. [{song['title']}]({song['url']}) ({song['duration']})"
                for i, song in enumerate(queue.get_queue()[:10])
            )
            embed.add_field(
                name=f"Up Next ({len(queue)} total)",
                value=queue_list or "Empty",
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.hybrid_command()
    async def pause(self, ctx: commands.Context):
        """Pause the current song"""
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send("Nothing is playing right now!", ephemeral=True)

        if ctx.voice_client.is_paused():
            return await ctx.send("Already paused!", ephemeral=True)

        ctx.voice_client.pause()
        await ctx.send("⏸️ Playback paused.")

    @commands.hybrid_command()
    async def resume(self, ctx: commands.Context):
        """Resume playback"""
        if not ctx.voice_client or not ctx.voice_client.is_paused():
            return await ctx.send("Nothing is paused right now!", ephemeral=True)

        ctx.voice_client.resume()
        await ctx.send("▶️ Playback resumed.")

    @commands.hybrid_command(aliases=['vol'])
    @app_commands.describe(volume="Volume level (0-200)")
    async def volume(self, ctx: commands.Context, volume: int):
        """Change the player's volume"""
        if not ctx.voice_client or not ctx.voice_client.source:
            return await ctx.send("Nothing is playing right now!", ephemeral=True)

        if not 0 <= volume <= 200:
            return await ctx.send("Volume must be between 0 and 200!", ephemeral=True)

        ctx.voice_client.source.volume = volume / 100
        await ctx.send(f"🔊 Volume set to {volume}%")

    @commands.hybrid_command()
    async def loop(self, ctx: commands.Context):
        """Toggle queue looping"""
        queue = self.get_queue(ctx.guild.id)
        queue.loop = not queue.loop

        if queue.loop_single and queue.loop:
            queue.loop_single = False

        await ctx.send(f"🔄 Queue looping {'enabled' if queue.loop else 'disabled'}")

    @commands.hybrid_command()
    async def loopsong(self, ctx: commands.Context):
        """Toggle current song looping"""
        queue = self.get_queue(ctx.guild.id)
        queue.loop_single = not queue.loop_single

        if queue.loop and queue.loop_single:
            queue.loop = False

        await ctx.send(f"🔂 Song looping {'enabled' if queue.loop_single else 'disabled'}")

    @commands.hybrid_command()
    async def shuffle(self, ctx: commands.Context):
        """Shuffle the queue"""
        queue = self.get_queue(ctx.guild.id)

        if len(queue) < 2:
            return await ctx.send("Need at least 2 songs to shuffle!", ephemeral=True)

        queue.shuffle()
        await ctx.send("🔀 Queue shuffled!")

    @commands.hybrid_command()
    @app_commands.describe(index="Position in queue (starting from 1)")
    async def remove(self, ctx: commands.Context, index: int):
        """Remove a song from the queue"""
        queue = self.get_queue(ctx.guild.id)

        if not 1 <= index <= len(queue):
            return await ctx.send(
                f"Invalid position! Queue has {len(queue)} songs.",
                ephemeral=True
            )

        song = queue.get_queue()[index-1]
        queue.remove(index-1)

        embed = discord.Embed(
            title="❌ Removed from Queue",
            description=f"[{song['title']}]({song['url']})",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command()
    async def leave(self, ctx: commands.Context):
        """Disconnect from voice channel"""
        if not ctx.voice_client:
            return await ctx.send("I'm not in a voice channel!", ephemeral=True)

        await ctx.voice_client.disconnect()

        if ctx.guild.id in self.queues:
            del self.queues[ctx.guild.id]

        await ctx.send("👋 Left the voice channel")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Handle bot being disconnected or left alone"""
        if member.id == self.bot.user.id and after.channel is None:
            # Bot was disconnected
            if before.channel and before.channel.guild.id in self.queues:
                del self.queues[before.channel.guild.id]
            return

        if (not member.bot and 
            before.channel and 
            before.channel.members and 
            len([m for m in before.channel.members if not m.bot]) == 0):

            # Everyone left the channel where bot is
            voice_client = discord.utils.get(self.bot.voice_clients, channel=before.channel)
            if voice_client:
                await voice_client.disconnect()

                if before.channel.guild.id in self.queues:
                    del self.queues[before.channel.guild.id]

async def setup(bot):
    await bot.add_cog(Music(bot))
