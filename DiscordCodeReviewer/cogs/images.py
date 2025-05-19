import discord
import logging
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from cogs import CovenTools
from config import MAX_IMAGES
from coven_ai import generate_image

class ImageGen(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_usage: Dict[int, Dict[str, Any]] = {}
        self.style_prompt = (
            "Digital painting, dark academia witch aesthetic, "
            "moody lighting, intricate details, vintage grimoire style, "
            "mystical atmosphere"
        )
        self._blacklisted_terms = {
            "nsfw", "nude", "sexual", "porn", "hentai",
            "violence", "gore", "blood", "hate", "racist"
        }
        self._prompt_enhancers = [
            "intricate details", "high resolution", "4k", 
            "dramatic lighting", "mystical atmosphere"
        ]

    async def _check_usage(self, user_id: int) -> tuple[bool, Optional[timedelta]]:
        """Returns (allowed, remaining_time) tuple"""
        user_data = self.user_usage.setdefault(user_id, {
            "count": 0,
            "last_reset": datetime.utcnow()
        })

        # Reset if new day
        if (datetime.utcnow() - user_data["last_reset"]) >= timedelta(days=1):
            user_data.update({"count": 0, "last_reset": datetime.utcnow()})

        if user_data["count"] >= MAX_IMAGES:
            remaining = timedelta(days=1) - (datetime.utcnow() - user_data["last_reset"])
            return (False, remaining)

        user_data["count"] += 1
        return (True, None)

    def _sanitize_prompt(self, prompt: str) -> tuple[bool, str]:
        """Returns (is_valid, sanitized_prompt)"""
        lower_prompt = prompt.lower()

        # Block blacklisted terms
        if any(term in lower_prompt for term in self._blacklisted_terms):
            return (False, "")

        # Enhance prompt
        enhanced = f"{prompt}, {', '.join(self._prompt_enhancers)}"
        return (True, enhanced[:400])  # Truncate to API limit

    @commands.hybrid_command(description="Generate witch-themed AI art")
    @commands.cooldown(1, 30, commands.BucketType.user)
    @CovenTools.in_channel("divination_den", "tea-spillage")
    async def imagine(self, ctx: commands.Context, *, prompt: str):
        """
        Generate magical artwork from your description

        Parameters
        ----------
        prompt: str
            What you want to generate (e.g. "witch reading ancient tome")
        """
        allowed, remaining = await self._check_usage(ctx.author.id)
        if not allowed:
            remaining_hours = remaining.seconds // 3600
            return await ctx.send(
                f"📸 Image quota exhausted ({MAX_IMAGES}/day). "
                f"Reset in {remaining_hours} hours.",
                ephemeral=True
            )

        is_valid, clean_prompt = self._sanitize_prompt(prompt)
        if not is_valid:
            return await ctx.send(
                "🔞 Prompt violates content guidelines.",
                ephemeral=True
            )

        try:
            # Show processing indicator
            msg = await ctx.send("🔮 Channeling creative energies...")

            # Generate with enhanced prompt using our centralized client
            image_url = await generate_image(f"{clean_prompt}", style=self.style_prompt)

            if not image_url:
                await msg.edit(content="❌ Image generation failed. Try a different prompt.")
                return

            # Build rich embed
            embed = discord.Embed(
                title=f"✨ {prompt[:96]}{'...' if len(prompt) > 96 else ''}",
                color=0x9B59B6,
                timestamp=datetime.utcnow()
            )
            embed.set_image(url=image_url)
            embed.set_footer(
                text=f"Requested by {ctx.author.display_name} • "
                     f"Generation {self.user_usage[ctx.author.id]['count']}/{MAX_IMAGES}"
            )

            await msg.edit(content=None, embed=embed)

        except Exception as e:
            await ctx.send(f"⚡ The magic backfired! {str(e)}", ephemeral=True)
            log = logging.getLogger(__name__)
            log.error(f"Image generation error: {e}")

    @commands.hybrid_command(description="Change the default art style")
    @CovenTools.is_warlock()
    @app_commands.describe(style="New style description (e.g. 'watercolor painting')")
    async def setstyle(self, ctx: commands.Context, *, style: str):
        """Update the base style for all image generations"""
        if len(style) > 500:
            return await ctx.send("❌ Style too long (max 500 chars)", ephemeral=True)

        self.style_prompt = style
        await ctx.send(
            embed=discord.Embed(
                title="🎨 Style Updated",
                description=f"```{style[:300]}...```",
                color=0x2ECC71
            ),
            ephemeral=True
        )

    @commands.hybrid_command(description="Reset a user's generation counter")
    @CovenTools.is_warlock()
    @app_commands.describe(user="User to reset")
    async def resetusage(self, ctx: commands.Context, user: discord.Member):
        """Admin command to refresh image quotas"""
        if user.id in self.user_usage:
            self.user_usage[user.id]["count"] = 0
            await ctx.send(
                f"🔄 Reset {user.mention}'s image counter (0/{MAX_IMAGES})",
                ephemeral=True
            )
        else:
            await ctx.send("ℹ️ User has no generations recorded", ephemeral=True)

    @commands.Cog.listener()
    async def on_coven_reset(self):
        """Handle daily reset event from coven cog"""
        self.user_usage.clear()

async def setup(bot):
    await bot.add_cog(ImageGen(bot))
