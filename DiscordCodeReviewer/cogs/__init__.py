import discord
from discord.ext import commands
from typing import Union, List, Optional, Callable, Dict, Any

class CovenTools:
    """Shared utilities for all cogs with performance optimizations"""

    _warlock_role_id = None
    _channel_configs = None

    @classmethod
    async def initialize(cls, bot):
        """Cache configs after bot is ready"""
        from config import WARLOCK_ROLE_ID
        from config.channels import CHANNEL_CONFIGS
        cls._warlock_role_id = WARLOCK_ROLE_ID
        cls._channel_configs = CHANNEL_CONFIGS

    @staticmethod
    def is_warlock():
        """Check if user has Warlock role (cached version)"""
        async def predicate(ctx):
            if CovenTools._warlock_role_id is None:
                await CovenTools.initialize(ctx.bot)
            return any(role.id == CovenTools._warlock_role_id 
                      for role in ctx.author.roles)
        return commands.check(predicate)

    @staticmethod
    def in_channel(*channel_names: str):
        """Restrict command to specific channels with cache"""
        async def predicate(ctx):
            if CovenTools._channel_configs is None:
                await CovenTools.initialize(ctx.bot)
            return (ctx.channel.name in channel_names or 
                    ctx.channel.id in (ch['id'] for name, ch in CovenTools._channel_configs.items()
                                     if name in channel_names))
        return commands.check(predicate)

    @staticmethod
    def has_whispers(min_whispers: int):
        """Check if user meets whisper threshold"""
        async def predicate(ctx):
            from cogs.coven import get_user_data  # Lazy import
            return get_user_data(ctx.author.id).get('whispers', 0) >= min_whispers
        return commands.check(predicate)

    @staticmethod
    async def prompt_confirm(ctx, message):
        """Ask for confirmation using a button"""
        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30.0)
                self.value = None

            @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
            async def confirm(self, interaction, button):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("This isn't your choice to make.", ephemeral=True)
                self.value = True
                await interaction.response.defer()
                self.stop()

            @discord.ui.button(label="No", style=discord.ButtonStyle.red)
            async def cancel(self, interaction, button):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("This isn't your choice to make.", ephemeral=True)
                self.value = False
                await interaction.response.defer()
                self.stop()

        view = ConfirmView()
        msg = await ctx.send(message, view=view)
        await view.wait()
        await msg.delete()
        return view.value

    @staticmethod
    def log_error(error_message):
        """Log error to console"""
        import logging
        log = logging.getLogger('bot')
        log.error(error_message)

# Decorator shortcuts
export = commands.check_any
cooldown = commands.cooldown

# Public exports
__all__ = ['export', 'cooldown', 'CovenTools']

# Auto-initialize when imported by bot
async def setup(bot):
    """Called by Discord.py during cog loading"""
    await CovenTools.initialize(bot)
    bot.coven_tools = CovenTools
