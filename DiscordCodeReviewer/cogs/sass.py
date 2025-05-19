import discord
import asyncio
import random
from discord.ext import commands
from discord import app_commands
from typing import Optional, List
from coven_ai import generate_wilhelmina_reply

class Sass(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._cooldowns = {}
        self._last_responses = {}
        self._provocation_task = None
        self.provocation_channels = []  # Will store channel IDs for random provocations
        self.provocation_chance = 0.15  # 15% chance of provoking after a message (when enabled)
        self.provocation_enabled = False  # Off by default

    def _cooldown_ok(self, user_id: int, seconds: int) -> bool:
        """Check and update cooldown status for a user"""
        now = discord.utils.utcnow().timestamp()
        if now - self._cooldowns.get(user_id, 0) < seconds:
            return False
        self._cooldowns[user_id] = now
        return True

    async def _generate_response(self, prompt: str, user_id: int) -> str:
        """Generate response while avoiding repeats"""
        response = await generate_wilhelmina_reply(prompt, user_id)

        # Ensure we don't repeat the same response
        if user_id in self._last_responses and self._last_responses[user_id] == response:
            response = await generate_wilhelmina_reply(prompt + " (provide a different response)", user_id)

        self._last_responses[user_id] = response
        return response

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Automatic responses to greetings, compliments, and random provocations"""
        if message.author.bot or not message.guild:
            return

        # Don't respond too frequently to the same user
        if not self._cooldown_ok(message.author.id, 60):
            return

        content = message.content.lower()

        # Check for greetings
        if any(word in content for word in ["hello", "hi", "hey", "greetings"]):
            prompt = (
                f"{message.author.display_name} has entered the room. "
                "Respond with your signature sass in 1-2 sentences."
            )
            reply = await self._generate_response(prompt, message.author.id)
            await message.reply(reply, mention_author=False)
            return

        # Check for compliments    
        if any(word in content for word in ["good bot", "nice", "great", "awesome", "love you"]):
            prompt = (
                f"{message.author.display_name} just complimented you. "
                "Respond sarcastically in 1-2 sentences."
            )
            reply = await self._generate_response(prompt, message.author.id)
            await message.reply(reply, mention_author=False)
            return

        # Random provocation chance (only in enabled channels)
        if (
            self.provocation_enabled
            and message.channel.id in self.provocation_channels
            and random.random() < self.provocation_chance
        ):  # 15% chance by default
            # Wait a bit to seem natural
            await asyncio.sleep(random.uniform(1.5, 4.0))

            # Choose a provocation type
            provocation_type = random.choice([
                "light_tease", "witchy_judgment", "backhanded_compliment", 
                "challenge", "cryptic_insight"
            ])

            if provocation_type == "light_tease":
                prompt = (
                    f"Tease {message.author.display_name} about something they just said: '{message.content}'. "
                    "Keep it light and playful, not truly mean. Use witchy sass in 1-2 sentences."
                )
            elif provocation_type == "witchy_judgment":
                prompt = (
                    f"As a centuries-old witch, judge {message.author.display_name}'s message: '{message.content}'. "
                    "Be dramatically judgmental but with subtle humor. 1-2 sentences."
                )
            elif provocation_type == "backhanded_compliment":
                prompt = (
                    f"Give {message.author.display_name} a backhanded compliment about: '{message.content}'. "
                    "Make it seem like praise at first but with a subtle sting. 1-2 sentences."
                )
            elif provocation_type == "challenge":
                prompt = (
                    f"Challenge {message.author.display_name}'s perspective on: '{message.content}'. "
                    "Be provocative but make them think. Use witchy wisdom in 1-2 sentences."
                )
            else:  # cryptic_insight
                prompt = (
                    f"Reveal a cryptic, slightly unnerving insight about {message.author.display_name} based on: '{message.content}'. "
                    "Be mysterious and make them wonder how you know. 1-2 sentences."
                )

            reply = await self._generate_response(prompt, message.author.id)
            await message.reply(reply, mention_author=True)  # Mention to ensure engagement

    @commands.hybrid_command()
    @commands.cooldown(1, 30, commands.BucketType.user)
    @app_commands.describe(member="Optional member to sass")
    async def sass(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Get a sassy response from Wilhelmina"""
        target = member or ctx.author
        prompt = (
            f"Give a savage but clever remark about {target.display_name} "
            "in 1-2 sentences. Maintain your witch persona."
        )
        reply = await self._generate_response(prompt, ctx.author.id)
        await ctx.send(reply)

    @commands.hybrid_command()
    @commands.cooldown(1, 30, commands.BucketType.user)
    @app_commands.describe(question="Your question for the sassy crystal ball")
    async def ask(self, ctx: commands.Context, *, question: str):
        """Consult the mystical crystal ball"""
        prompt = (
            f"{ctx.author.display_name} asks: '{question}'. "
            "Respond like a mystical, sarcastic fortune teller in 1-3 sentences."
        )
        reply = await self._generate_response(prompt, ctx.author.id)
        embed = discord.Embed(
            title="🔮 Crystal Ball Says...",
            description=reply,
            color=0x9B59B6
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command()
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def roast(self, ctx: commands.Context, member: discord.Member):
        """Roast another user (all in good fun)"""
        if member == ctx.author:
            return await ctx.send("I admire your self-loathing, but no.", ephemeral=True)

        prompt = (
            f"Roast {member.display_name} with elegant cruelty in 1-2 sentences. "
            "Maintain your sophisticated witch persona."
        )
        reply = await self._generate_response(prompt, ctx.author.id)
        await ctx.send(reply)

    @commands.hybrid_command()
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def compliment(self, ctx: commands.Context, member: discord.Member):
        """Give a backhanded compliment"""
        if member == ctx.author:
            return await ctx.send("You're fishing for it, aren't you?", ephemeral=True)

        prompt = (
            f"Give {member.display_name} a backhanded compliment "
            "in 1-2 sentences. Sound polite but cutting."
        )
        reply = await self._generate_response(prompt, ctx.author.id)
        await ctx.send(reply)

    @commands.hybrid_command()
    @commands.cooldown(1, 45, commands.BucketType.user)
    @app_commands.describe(text="Text to witchify")
    async def witchify(self, ctx: commands.Context, *, text: str):
        """Make your text sound more witchy"""
        prompt = (
            f"Rewrite this text in the style of a gothic witch: '{text}'. "
            "Use archaic language and witchy metaphors. Keep it under 200 characters."
        )
        reply = await self._generate_response(prompt, ctx.author.id)
        await ctx.send(reply)

    @commands.hybrid_command()
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def tarot(self, ctx: commands.Context):
        """Get a sassy tarot reading"""
        prompt = (
            "Draw one tarot card and give a sarcastic interpretation "
            "in 2-3 sentences. Include the card name and meaning."
        )
        reply = await self._generate_response(prompt, ctx.author.id)
        embed = discord.Embed(
            title="🃏 Your Tarot Reading",
            description=reply,
            color=0x8A2BE2
        )
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        """Handle command errors with witchy flair"""
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"🕰️ The spirits are exhausted. Try again in {int(error.retry_after)} seconds.",
                ephemeral=True
            )
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send(
                "🔮 The coven denies you permission, sweetling.",
                ephemeral=True
            )
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send(
                "🔍 The mists reveal no such fool in this realm.",
                ephemeral=True
            )

    @commands.group(name="provoke", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def provoke_group(self, ctx):
        """Control Wilhelmina's random provocations (Admin only)"""
        status = "enabled" if self.provocation_enabled else "disabled"
        channels = [f"<#{ch_id}>" for ch_id in self.provocation_channels] or ["None"]

        embed = discord.Embed(
            title="🔥 Provocation Settings",
            description=f"Wilhelmina's random sass is currently **{status}**.",
            color=0xC71585
        )
        embed.add_field(
            name="Active in Channels",
            value=", ".join(channels),
            inline=False
        )
        embed.add_field(
            name="Chance",
            value=f"{int(self.provocation_chance * 100)}% per eligible message",
            inline=False
        )
        embed.add_field(
            name="Available Commands",
            value=(
                "`!provoke enable` - Turn provocations on\n"
                "`!provoke disable` - Turn provocations off\n"
                "`!provoke channel [add/remove] [#channel]` - Manage channels\n"
                "`!provoke chance [1-50]` - Set provocation percentage"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @provoke_group.command(name="enable")
    @commands.has_permissions(administrator=True)
    async def provoke_enable(self, ctx):
        """Enable Wilhelmina's random provocations"""
        if self.provocation_enabled:
            return await ctx.send("The pot is already bubbling, dearie. I'm already enabled to cause chaos.")

        if not self.provocation_channels:
            await ctx.send("⚠️ Warning: No channels set for provocations. Use `!provoke channel add #channel` first.")

        self.provocation_enabled = True
        await ctx.send("😈 Excellent choice. I shall now randomly sass your members. Let the games begin...")

    @provoke_group.command(name="disable")
    @commands.has_permissions(administrator=True)
    async def provoke_disable(self, ctx):
        """Disable Wilhelmina's random provocations"""
        if not self.provocation_enabled:
            return await ctx.send("I'm already holding my tongue, darling. The provocations are disabled.")

        self.provocation_enabled = False
        await ctx.send("😒 Fine. I'll keep my observations to myself. For now...")

    @provoke_group.group(name="channel", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def provoke_channel(self, ctx):
        """Manage provocation channels"""
        channels = [f"<#{ch_id}>" for ch_id in self.provocation_channels] or ["None configured"]
        await ctx.send(f"**Active provocation channels:** {', '.join(channels)}")

    @provoke_channel.command(name="add")
    @commands.has_permissions(administrator=True)
    async def provoke_channel_add(self, ctx, channel: discord.TextChannel):
        """Add a channel to provocation list"""
        if channel.id in self.provocation_channels:
            return await ctx.send(f"I already have my eye on {channel.mention}, dear.")

        self.provocation_channels.append(channel.id)
        await ctx.send(f"✅ I'll now occasionally stir the pot in {channel.mention}. How delightful.")

    @provoke_channel.command(name="remove")
    @commands.has_permissions(administrator=True)
    async def provoke_channel_remove(self, ctx, channel: discord.TextChannel):
        """Remove a channel from provocation list"""
        if channel.id not in self.provocation_channels:
            return await ctx.send(f"I'm not watching {channel.mention} anyway, sweetling.")

        self.provocation_channels.remove(channel.id)
        await ctx.send(f"✅ I'll leave {channel.mention} in peace. For now...")

    @provoke_group.command(name="chance")
    @commands.has_permissions(administrator=True)
    async def provoke_chance(self, ctx, percentage: int):
        """Set provocation chance (1-50)%"""
        if not 1 <= percentage <= 50:
            return await ctx.send("The percentage must be between 1 and 50%, darling. Let's not go mad with power.")

        self.provocation_chance = percentage / 100
        await ctx.send(f"🎲 I'll now provoke with a {percentage}% chance. {'Perfect!' if percentage > 30 else 'How sensible of you.'}")

    # Additional fun command to directly provoke someone
    @commands.command()
    @commands.cooldown(1, 300, commands.BucketType.user)
    @commands.has_permissions(administrator=True)
    async def instigate(self, ctx, member: discord.Member, *, topic: Optional[str] = None):
        """Provoke a specific member for fun (Admin Only)"""
        if member.bot:
            return await ctx.send("I don't provoke my fellow constructs, darling.")

        # Delete the command message to make it seem spontaneous
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

        topic_text = f" about {topic}" if topic else ""

        prompt = (
            f"Spontaneously provoke an argument with {member.display_name}{topic_text}. "
            "Be witty, slightly insulting but in a fun way that invites a comeback. "
            "Make a statement that would get them to defend themselves or engage. "
            "Keep it playful but provocative in 1-2 sentences."
        )

        reply = await self._generate_response(prompt, ctx.author.id)

        # If in a thread, reply to the thread. Otherwise, create a new message
        await ctx.channel.send(f"{member.mention} {reply}")

async def setup(bot):
    await bot.add_cog(Sass(bot))
