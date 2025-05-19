import discord
import logging
import asyncio
from typing import Dict, List, Optional, Union
from discord.ext import commands

# Initialize logging
log = logging.getLogger(__name__)

# Default channel configuration 
DEFAULT_CHANNELS = [
    # Category: 🔮 COVEN GROUNDS
    {
        "type": "category",
        "name": "🔮 COVEN GROUNDS",
        "children": [
            {"type": "text", "name": "welcome", "topic": "Greet new members of the coven"},
            {"type": "text", "name": "announcements", "topic": "Important coven news and events"},
            {"type": "text", "name": "rules", "topic": "Guidelines for all coven members"},
            {"type": "text", "name": "roles", "topic": "Assign yourself roles and climb the ranks"}
        ]
    },
    # Category: 💬 WITCHY CONVERSATIONS
    {
        "type": "category",
        "name": "💬 WITCHY CONVERSATIONS",
        "children": [
            {"type": "text", "name": "general", "topic": "General coven discussions"},
            {"type": "text", "name": "witchcraft", "topic": "Share your spells and magical knowledge"},
            {"type": "text", "name": "tea-circle", "topic": "Gossip and casual conversations"},
            {"type": "text", "name": "media", "topic": "Share images, videos, and other media"}
        ]
    },
    # Category: 🎭 ENTERTAINMENT
    {
        "type": "category",
        "name": "🎭 ENTERTAINMENT",
        "children": [
            {"type": "text", "name": "memes", "topic": "Share your best witchy memes"},
            {"type": "text", "name": "bot-commands", "topic": "Use Wilhelmina's commands here"},
            {"type": "text", "name": "art-gallery", "topic": "Share artwork and creations"}
        ]
    },
    # Category: 🔊 VOICE CHAMBERS
    {
        "type": "category",
        "name": "🔊 VOICE CHAMBERS",
        "children": [
            {"type": "voice", "name": "Ritual Circle"},
            {"type": "voice", "name": "Cauldron Room"},
            {"type": "voice", "name": "Crystal Chamber"},
            {"type": "voice", "name": "Music Séance"}
        ]
    },
    # Category: 🔒 WARLOCKS ONLY
    {
        "type": "category",
        "name": "🔒 WARLOCKS ONLY",
        "permissions": {"public": False, "warlock": True, "admin": True},
        "children": [
            {"type": "text", "name": "mod-chat", "topic": "Discussions for moderators"},
            {"type": "text", "name": "mod-logs", "topic": "Records of moderation actions"},
            {"type": "text", "name": "bot-config", "topic": "Configure Wilhelmina here"}
        ]
    }
]

# Default role configuration
DEFAULT_ROLES = [
    # Admin role
    {
        "name": "Warlock",
        "color": discord.Color.dark_purple(),
        "hoist": True,
        "mentionable": True,
        "permissions": discord.Permissions(administrator=True),
        "position": 6
    },
    # Moderator role
    {
        "name": "High Priest/Priestess",
        "color": discord.Color.purple(),
        "hoist": True,
        "mentionable": True,
        "permissions": discord.Permissions(
            manage_messages=True,
            kick_members=True,
            ban_members=True,
            manage_nicknames=True,
            mute_members=True,
            move_members=True
        ),
        "position": 5
    },
    # Active members
    {
        "name": "Shadow Inquisitor",
        "color": discord.Color.dark_magenta(),
        "hoist": True,
        "mentionable": True,
        "permissions": discord.Permissions(
            add_reactions=True,
            stream=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
            external_emojis=True
        ),
        "position": 4
    },
    # Regular members
    {
        "name": "Seer",
        "color": discord.Color.dark_teal(),
        "hoist": True,
        "mentionable": True,
        "permissions": discord.Permissions(
            add_reactions=True,
            send_messages=True,
            embed_links=True,
            attach_files=True
        ),
        "position": 3
    },
    # Beginner members
    {
        "name": "Neophyte",
        "color": discord.Color.greyple(),
        "hoist": True,
        "mentionable": True,
        "permissions": discord.Permissions(
            add_reactions=True,
            send_messages=True
        ),
        "position": 2
    },
    # Muted role
    {
        "name": "Silenced",
        "color": discord.Color.dark_grey(),
        "hoist": False,
        "mentionable": False,
        "permissions": discord.Permissions(
            read_messages=True,
            read_message_history=True
        ),
        "position": 1
    }
]

class SetupWizard(discord.ui.View):
    def __init__(self, owner: discord.Member):
        super().__init__(timeout=300.0)  # 5 minute timeout
        self.owner = owner
        self.result = None

    @discord.ui.button(label="Standard Coven", style=discord.ButtonStyle.primary)
    async def standard_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.owner:
            return await interaction.response.send_message("Only server admins can use this setup.", ephemeral=True)

        self.result = "standard"
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Minimalist Setup", style=discord.ButtonStyle.secondary)
    async def minimal_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.owner:
            return await interaction.response.send_message("Only server admins can use this setup.", ephemeral=True)

        self.result = "minimal"
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.owner:
            return await interaction.response.send_message("Only server admins can use this setup.", ephemeral=True)

        self.result = "cancel"
        self.stop()
        await interaction.response.defer()

    async def on_timeout(self):
        self.result = "timeout"
        self.stop()

class ServerSetup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.setup_in_progress = set()  # Track guilds with ongoing setup

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Auto-triggers when the bot joins a new server"""
        log.info(f"Joined new guild: {guild.name} (ID: {guild.id})")

        # Check if we can find a system channel or default channel
        target_channel = guild.system_channel
        if not target_channel:
            # Find the first channel we can send messages to
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    target_channel = channel
                    break

        if not target_channel:
            log.error(f"Could not find a channel to send welcome message in {guild.name}")
            return

        try:
            # Send welcome message with setup option
            embed = discord.Embed(
                title="✨ Wilhelmina has joined your server! ✨",
                description=(
                    "Greetings, mortals. I am **Wilhelmina**, a witchy Discord companion with "
                    "centuries of arcane knowledge at my disposal.\n\n"
                    "Would you like me to prepare your server with a magical theme, "
                    "complete with channels and roles for your coven?\n\n"
                    "The server owner may select an option below."
                ),
                color=0x9B59B6
            )
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            embed.add_field(
                name="Standard Coven", 
                value="Full magical setup with categories, channels, and roles", 
                inline=False
            )
            embed.add_field(
                name="Minimalist Setup", 
                value="Just the essential channels and roles", 
                inline=False
            )
            embed.set_footer(text="This setup can only be initiated by server administrators")

            # Create view with setup options
            view = SetupWizard(guild.owner)
            msg = await target_channel.send(embed=embed, view=view)

            # Wait for response
            await view.wait()

            if view.result == "standard":
                # Start full setup
                await self._perform_setup(guild, target_channel, "standard")
            elif view.result == "minimal":
                # Start minimal setup
                await self._perform_setup(guild, target_channel, "minimal") 
            elif view.result == "cancel":
                await msg.edit(content="Server setup cancelled. You can run `/setup` at any time.", view=None, embed=None)
            else:  # timeout
                await msg.edit(content="Setup wizard timed out. You can run `/setup` at any time.", view=None, embed=None)

        except Exception as e:
            log.error(f"Error in welcome message: {e}")

    @commands.hybrid_command(name="setup")
    @commands.has_permissions(administrator=True)
    async def setup_command(self, ctx: commands.Context):
        """Initialize or re-configure server with coven theme"""
        # Check if setup is already running in this guild
        if ctx.guild.id in self.setup_in_progress:
            return await ctx.send("A setup is already in progress for this server.", ephemeral=True)

        embed = discord.Embed(
            title="🔮 Wilhelmina's Server Setup",
            description=(
                "I can transform your server with a witchy coven theme, "
                "creating all the necessary channels and roles.\n\n"
                "**Warning:** This may overwrite existing channels if they have the same names."
            ),
            color=0x9B59B6
        )
        embed.add_field(
            name="Standard Coven", 
            value="Full magical setup with categories, channels, and roles", 
            inline=False
        )
        embed.add_field(
            name="Minimalist Setup", 
            value="Just the essential channels and roles", 
            inline=False
        )

        # Create view with setup options
        view = SetupWizard(ctx.author)
        await ctx.send(embed=embed, view=view)

        # Wait for response
        await view.wait()

        if view.result == "standard":
            # Start full setup
            await self._perform_setup(ctx.guild, ctx.channel, "standard")
        elif view.result == "minimal":
            # Start minimal setup
            await self._perform_setup(ctx.guild, ctx.channel, "minimal")
        elif view.result == "cancel":
            await ctx.send("Server setup cancelled.")
        else:  # timeout
            await ctx.send("Setup wizard timed out.")

    async def _perform_setup(self, guild: discord.Guild, channel: discord.TextChannel, setup_type: str):
        """Perform the actual server setup"""
        if guild.id in self.setup_in_progress:
            return await channel.send("A setup is already in progress for this server.")

        try:
            self.setup_in_progress.add(guild.id)

            status_message = await channel.send("🧙‍♀️ Beginning server transformation... ✨")

            # Create roles (reversed to handle hierarchy properly)
            role_map = {}
            _ = await status_message.edit(content="🧙‍♀️ Creating roles... ✨")

            for role_config in reversed(DEFAULT_ROLES):
                # Skip some roles for minimal setup
                if setup_type == "minimal" and role_config["name"] in ["High Priest/Priestess", "Shadow Inquisitor"]:
                    continue

                # Check if role already exists
                existing_role = discord.utils.get(guild.roles, name=role_config["name"])
                if existing_role:
                    role_map[role_config["name"]] = existing_role
                    continue

                try:
                    role = await guild.create_role(
                        name=role_config["name"],
                        color=role_config["color"],
                        hoist=role_config["hoist"],
                        mentionable=role_config["mentionable"], 
                        permissions=role_config["permissions"]
                    )
                    # Sleep briefly to avoid rate limits
                    await asyncio.sleep(1)
                    role_map[role_config["name"]] = role
                except Exception as e:
                    log.error(f"Error creating role {role_config['name']}: {e}")

            # Get the key roles
            warlock_role = role_map.get("Warlock")
            silenced_role = role_map.get("Silenced")

            # Create channels
            channel_list = DEFAULT_CHANNELS
            if setup_type == "minimal":
                # Use a subset of channels for minimal setup
                channel_list = [c for c in DEFAULT_CHANNELS 
                               if c["name"] in ["🔮 COVEN GROUNDS", "💬 WITCHY CONVERSATIONS", "🔊 VOICE CHAMBERS"]]

            await status_message.edit(content="🧙‍♀️ Creating channels... ✨")

            for category_config in channel_list:
                # Set up permissions
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=True),
                }

                # Add role-specific overwrites
                if "permissions" in category_config:
                    perms = category_config["permissions"]

                    # Add warlock/admin overwrites
                    if perms.get("public") is False and perms.get("warlock") is True and warlock_role:
                        overwrites[guild.default_role] = discord.PermissionOverwrite(read_messages=False)
                        overwrites[warlock_role] = discord.PermissionOverwrite(read_messages=True)

                # Add silenced role overwrites for everything
                if silenced_role:
                    overwrites[silenced_role] = discord.PermissionOverwrite(
                        send_messages=False, 
                        add_reactions=False,
                        speak=False
                    )

                try:
                    # Create the category
                    category = await guild.create_category(
                        name=category_config["name"],
                        overwrites=overwrites
                    )

                    # Sleep briefly to avoid rate limits
                    await asyncio.sleep(1)

                    # Create channels under this category
                    for child_config in category_config.get("children", []):
                        try:
                            if child_config["type"] == "text":
                                await guild.create_text_channel(
                                    name=child_config["name"],
                                    category=category,
                                    topic=child_config.get("topic", "")
                                )
                            elif child_config["type"] == "voice":
                                await guild.create_voice_channel(
                                    name=child_config["name"],
                                    category=category
                                )

                            # Sleep briefly to avoid rate limits
                            await asyncio.sleep(0.5)

                        except Exception as e:
                            log.error(f"Error creating channel {child_config['name']}: {e}")

                except Exception as e:
                    log.error(f"Error creating category {category_config['name']}: {e}")

            # Create welcome message in the welcome channel
            welcome_channel = discord.utils.get(guild.text_channels, name="welcome")
            if welcome_channel:
                # Update rules channel with server rules
                try:
                    rules_text = (
                        "# 🔮 Welcome to the Coven! 🔮\n\n"
                        "Our mystical community is now protected and enhanced by Wilhelmina, "
                        "a witchy Discord bot with sass and magical powers!\n\n"
                        "## Getting Started\n"
                        "- Use `/myrank` to check your current status and whispers\n"
                        "- Chat in our channels to earn whispers and rise through the ranks\n"
                        "- Visit <#bot-commands> to try tarot readings, images, and more\n\n"
                        "## Rank System\n"
                        "- **Neophyte**: New members (0-49 whispers)\n"
                        "- **Seer**: Regular members (50-199 whispers)\n"
                        "- **Shadow Inquisitor**: Trusted members (200-499 whispers)\n"
                        "- **High Priest/Priestess**: Elite members (500+ whispers)\n"
                        "- **Warlock**: Server administrators\n\n"
                        "May your time in our coven be magical! ✨"
                    )
                    await welcome_channel.send(rules_text)
                except Exception as e:
                    log.error(f"Error sending welcome message: {e}")

            # Finalize
            await status_message.edit(
                content=(
                    "✅ Server transformation complete! Your mystical coven has been prepared.\n\n"
                    "**Next Steps:**\n"
                    "• Review and arrange channels and roles as needed\n"
                    "• Set up server rules in the rules channel\n"
                    "• Try `/help` to see available commands\n\n"
                    "Thank you for adding Wilhelmina to your server! 🧙‍♀️✨"
                )
            )

        except Exception as e:
            log.error(f"Error during server setup: {e}")
            await channel.send(f"⚠️ Something went wrong during setup: {e}")
        finally:
            self.setup_in_progress.remove(guild.id)

async def setup(bot):
    await bot.add_cog(ServerSetup(bot))
