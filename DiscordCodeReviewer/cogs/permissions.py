import discord
from discord.ext import commands
from typing import Dict, List, Optional, Set
import logging
from datetime import datetime

# Initialize logging
log = logging.getLogger(__name__)

class Permissions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.role_choices = ["high_priest", "high_priestess"]
        self.base_permissions = {
            "music": {
                "skip_votes": 1,
                "max_queue": 3,
                "can_play": True
            }
        }

        self.role_permissions = {
            "neophyte": {
                "tarot": {"daily_limit": 1, "channels": ["divination-den"]},
                "images": {"daily_limit": 1, "nsfw_allowed": False},
                "sass": {"daily_limit": 3}
            },
            "seer": {
                "tarot": {"daily_limit": 2, "channels": ["divination-den", "tea-spillage"]},
                "images": {"daily_limit": 3, "nsfw_allowed": False},
                "sass": {"daily_limit": 5}
            },
            "acolyte": {
                "tarot": {"daily_limit": 3, "channels": ["divination-den", "tea-spillage"]},
                "images": {"daily_limit": 5, "nsfw_allowed": False},
                "sass": {"daily_limit": 10}
            },
            "soothsayer": {
                "tarot": {"daily_limit": 5, "channels": ["divination-den", "tea-spillage"]},
                "images": {"daily_limit": 10, "nsfw_allowed": True},
                "sass": {"daily_limit": 20}
            },
            "high_priest": {
                "tarot": {"daily_limit": 10, "channels": ["divination-den", "tea-spillage"], "bypass_cooldown": True},
                "images": {"daily_limit": 20, "nsfw_allowed": True},
                "sass": {"daily_limit": 50, "bypass_cooldown": True}
            },
            "high_priestess": {
                "tarot": {"daily_limit": 10, "channels": ["divination-den", "tea-spillage"], "bypass_cooldown": True},
                "images": {"daily_limit": 20, "nsfw_allowed": True},
                "sass": {"daily_limit": 50, "bypass_cooldown": True}
            },
            "warlock_sorcerer": {
                "bypass_all": True
            }
        }

        self.channel_permissions = {
            "tea-spillage": {
                "required_role": "seer",
                "blacklisted_commands": ["imagine", "ban"]
            },
            "divination-den": {
                "allowed_commands": ["tarot", "interpret"],
                "delete_non_commands": True
            }
        }

    @staticmethod
    def get_user_permission_level(member: discord.Member) -> str:
        user_roles = [role.name.lower() for role in member.roles]
        for role in ["warlock_sorcerer", "high_priest", "high_priestess", "soothsayer", "acolyte", "seer"]:
            if role in user_roles:
                return "high_priest" if role in ["high_priest", "high_priestess"] else role
        return "neophyte"

    async def check_daily_limit(self, member: discord.Member, feature: str, limit: int) -> bool:
        try:
            user_id = str(member.id)
            today = datetime.utcnow().date()

            if not hasattr(self, '_usage_tracking'):
                self._usage_tracking = {}

            if user_id not in self._usage_tracking:
                self._usage_tracking[user_id] = {'last_checked': today, 'usage': {}}

            user_data = self._usage_tracking[user_id]

            if 'last_checked' not in user_data or user_data['last_checked'] != today:
                user_data['last_checked'] = today
                user_data['usage'] = {}

            if 'usage' not in user_data:
                user_data['usage'] = {}

            current_usage = user_data['usage'].get(feature, 0)
            return current_usage < limit

        except Exception as e:
            log.error(f"Error checking daily limit for {member}: {e}")
            return False

    async def increment_usage(self, member: discord.Member, feature: str):
        try:
            user_id = str(member.id)
            if not hasattr(self, '_usage_tracking'):
                self._usage_tracking = {}

            if user_id not in self._usage_tracking:
                self._usage_tracking[user_id] = {'last_checked': datetime.utcnow().date(), 'usage': {}}

            if 'usage' not in self._usage_tracking[user_id]:
                self._usage_tracking[user_id]['usage'] = {}

            self._usage_tracking[user_id]['usage'][feature] = self._usage_tracking[user_id]['usage'].get(feature, 0) + 1

        except Exception as e:
            log.error(f"Error incrementing usage for {member}: {e}")

    @commands.command(name="choose_title")
    @commands.guild_only()
    @commands.has_role("soothsayer")
    async def choose_title(self, ctx, title: str = None):
        if not ctx.guild:
            return await ctx.send("❌ This command can only be used in a server.")

        try:
            user_roles = [role.name.lower() for role in ctx.author.roles]
            has_high_rank = any(role in user_roles for role in ["high_priest", "high_priestess"])
            if has_high_rank:
                return await ctx.send("🔮 You have already chosen your title!")

            if not title or title.lower() not in self.role_choices:
                choices = "\n".join(f"• `{role}`" for role in self.role_choices)
                return await ctx.send(
                    f"🔮 You've reached the final tier! Choose your title with `!choose_title <title>`\n\n"
                    f"Available titles (case sensitive):\n{choices}"
                )

            title = title.lower()
            if title not in self.role_choices:
                return await ctx.send("❌ Invalid title choice. Please choose either 'high_priest' or 'high_priestess'.")

            guild = ctx.guild
            target_role = discord.utils.get(guild.roles, name=title)
            soothsayer_role = discord.utils.get(guild.roles, name="soothsayer")

            if not target_role:
                try:
                    target_role = await guild.create_role(
                        name=title,
                        color=discord.Color.purple(),
                        reason=f"Auto-creating {title} role for {ctx.author}",
                        permissions=discord.Permissions(
                            read_messages=True,
                            send_messages=True,
                            read_message_history=True
                        )
                    )
                    bot_member = guild.get_member(self.bot.user.id)
                    if bot_member.roles:
                        await target_role.edit(position=len(bot_member.roles) - 1)
                except discord.Forbidden:
                    return await ctx.send("❌ I don't have permission to create the required role.")
                except discord.HTTPException as e:
                    log.error(f"Error creating role {title}: {e}")
                    return await ctx.send("❌ Failed to create the role. Please try again later.")

            try:
                await ctx.author.add_roles(target_role, reason="Title selection")
                if soothsayer_role:
                    await ctx.author.remove_roles(soothsayer_role, reason="Title promotion")

                try:
                    await ctx.author.send(
                        f"✨ You are now a {target_role.name}! May your wisdom guide us all.\n"
                        f"You now have access to all features with increased limits."
                    )
                except discord.Forbidden:
                    pass

                await ctx.send(f"✨ {ctx.author.mention} has been promoted to {target_role.name}!")

            except discord.Forbidden:
                await ctx.send("❌ I don't have permission to modify roles. Please check my role hierarchy.")
            except discord.HTTPException as e:
                log.error(f"Error modifying roles: {e}")
                await ctx.send("❌ Failed to update roles. Please try again later.")

        except Exception as e:
            log.error(f"Error in choose_title: {e}", exc_info=True)
            await ctx.send("❌ An error occurred while processing your request. Please try again later.")

    async def check_permissions(self, ctx: commands.Context) -> bool:
        if await self.bot.is_owner(ctx.author):
            return True

        user_permission_level = self.get_user_permission_level(ctx.author)
        channel_name = getattr(ctx.channel, "name", "").lower()

        if channel_name in self.channel_permissions:
            channel_rules = self.channel_permissions[channel_name]

            if "required_role" in channel_rules and \
               channel_rules["required_role"] not in [r.name.lower() for r in ctx.author.roles]:
                await ctx.send("🔒 You don't have permission to use commands in this channel.", delete_after=10)
                return False

            if "blacklisted_commands" in channel_rules and \
               ctx.command.name in channel_rules["blacklisted_commands"]:
                await ctx.send("🚫 This command is not allowed in this channel.", delete_after=10)
                return False

            if "allowed_commands" in channel_rules and \
               ctx.command.name not in channel_rules["allowed_commands"]:
                await ctx.send("❌ This command is not allowed in this channel.", delete_after=10)
                return False

        cog_name = ctx.command.cog_name.lower() if ctx.command.cog else ""
        if cog_name == "music":
            return True

        role_perms = self.role_permissions.get(user_permission_level, {})
        if role_perms.get("bypass_all", False):
            return True

        cog_perms = role_perms.get(cog_name, {})

        if "channels" in cog_perms and channel_name not in cog_perms["channels"]:
            allowed_channels = ", ".join(f"#{c}" for c in cog_perms["channels"])
            await ctx.send(f"🔍 This command can only be used in: {allowed_channels}", delete_after=10)
            return False

        if "daily_limit" in cog_perms and not await self.check_daily_limit(ctx.author, cog_name, cog_perms["daily_limit"]):
            await ctx.send(f"⏳ You've reached your daily limit for {cog_name} commands.", delete_after=10)
            return False

        return True

    @commands.Cog.listener()
    async def on_command(self, ctx):
        if not ctx.command:
            return

        if not await self.check_permissions(ctx):
            channel_name = getattr(ctx.channel, "name", "").lower()
            if channel_name in self.channel_permissions and \
               self.channel_permissions[channel_name].get("delete_non_commands", False):

                try:
                    await ctx.message.delete()
                except (discord.Forbidden, discord.NotFound):
                    pass

async def setup(bot):
    await bot.add_cog(Permissions(bot))
