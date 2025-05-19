from discord.ext import commands
from typing import Optional
from config import (
    MAX_IMAGES,
    TAROT_COOLDOWN
)
from coven_ai import generate_wilhelmina_reply, generate_image

class AI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._image_counts = {}  # {user_id: count}

    async def reset_counts(self):
        """Daily count reset logic"""
        for user_id in list(self._image_counts.keys()):
            self._image_counts[user_id] = 0

    @commands.hybrid_command()
    @commands.cooldown(1, TAROT_COOLDOWN, commands.BucketType.user)
    async def ask(self, ctx, *, question: str):
        """Get AI-generated wisdom"""
        if len(question) > 1000:
            return await ctx.send("❌ Question too long (max 1000 characters).")
        await ctx.defer()
        response = await generate_wilhelmina_reply(question)
        await ctx.send(response)

    @commands.hybrid_command()
    async def imagine(self, ctx, *, prompt: str):
        """Generate an image from a prompt (max {MAX_IMAGES} per day)"""
        user_id = ctx.author.id
        count = self._image_counts.get(user_id, 0)
        if count >= MAX_IMAGES:
            return await ctx.send("🖼️ You've reached your image limit for today.")
        await ctx.defer()
        image = await generate_image(prompt)
        self._image_counts[user_id] = count + 1
        await ctx.send(file=image)

async def setup(bot):
    cog = AI(bot)
    await bot.add_cog(cog)
    bot.loop.create_task(cog.reset_counts())  # Now safe and DeepSource-approved
