from discord import app_commands
import discord
import asyncio
import random
import datetime
from discord.ext import commands
from typing import Optional
from .. import CovenTools

class Onboarding(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.welcome_messages = [
            "A wild {member.mention} has appeared in the coven!",
            "Welcome to the coven, {member.mention}! We've been expecting you...",
            "The stars have aligned! {member.mention} has joined us!",
            "Hearken! {member.mention} has entered the sacred circle!",
            "A new witch joins our ranks! Welcome, {member.mention}!",
            "The cauldron bubbles... {member.mention} has arrived!",
            "By the light of the full moon, we welcome {member.mention}!",
            "The spirits whisper your name, {member.mention}. Welcome!",
            "The coven grows stronger with {member.mention}'s arrival!",
            "Draw the circle, light the candles, {member.mention} is here!"
        ]

        self.farewell_messages = [
            "The veil parts as {member.name} leaves our circle...",
            "The cauldron dims as {member.name} departs...",
            "Until we meet again under the full moon, {member.name}...",
            "The spirits whisper {member.name}'s name as they leave...",
            "The circle remains unbroken, though {member.name} has left us...",
            "The wind carries {member.name} away from our midst...",
            "The stars dim slightly as {member.name} departs...",
            "The coven is less one as {member.name} takes their leave...",
            "The candles flicker as {member.name} steps beyond our circle...",
            "The Book of Shadows closes on {member.name}'s chapter with us..."
        ]

        self.rules = [
            "1. **Respect All Members** - Treat everyone with kindness and respect. No harassment, discrimination, or hate speech will be tolerated.",
            "2. **No NSFW Content** - Keep all content appropriate for all ages.",
            "3. **No Spam or Self-Promotion** - This includes unsolicited DMs and excessive mentions.",
            "4. **Keep It On Topic** - Respect channel purposes and keep discussions relevant.",
            "5. **No Illegal Content** - Sharing or requesting pirated material is not allowed.",
            "6. **Respect Privacy** - Do not share personal information about yourself or others.",
            "7. **Use Appropriate Channels** - Keep discussions in their respective channels.",
            "8. **No Begging** - This includes begging for roles, promotions, or special treatment.",
            "9. **Follow Discord's TOS** - All Discord rules apply here as well.",
            "10. **Have Fun!** - This is a community, so relax and enjoy your time with us!"
        ]

        self.faq = {
            "How do I get roles?": "Use the `/roles` command to see available roles and how to get them!",
            "How do I report a problem?": "Please DM a moderator or use the report feature if you encounter any issues.",
            "Can I invite my friends?": "Absolutely! Just make sure they follow the server rules.",
            "How do I get help with the bot?": "Use the `/help` command or ask in the support channel!",
            "What are the server's rules?": "Check out the #rules channel for all the details!"
        }

        self._welcome_dms_enabled = True
        self._welcome_messages_enabled = True
        self._welcome_roles = set()
        self._welcome_channel = None
        self._rules_channel = None
        self._member_count_channel = None

        # Load configuration
        self.bot.loop.create_task(self._load_config())

    async def _load_config(self):
        """Load configuration from database"""
        await self.bot.wait_until_ready()

        # Load welcome roles
        self._welcome_roles = set(await self.bot.db.get_welcome_roles())

        # Load channel settings
        self._welcome_channel = await self.bot.db.get_setting("welcome_channel")
        self._rules_channel = await self.bot.db.get_setting("rules_channel")
        self._member_count_channel = await self.bot.db.get_setting("member_count_channel")

        # Load toggle settings
        self._welcome_dms_enabled = await self.bot.db.get_setting("welcome_dms_enabled", default=True)
        self._welcome_messages_enabled = await self.bot.db.get_setting("welcome_messages_enabled", default=True)

    async def _send_welcome_message(self, member: discord.Member):
        """Send welcome message to the welcome channel"""
        if not self._welcome_messages_enabled or not self._welcome_channel:
            return

        channel = member.guild.get_channel(int(self._welcome_channel))
        if not channel:
            return

        # Get a random welcome message
        message = random.choice(self.welcome_messages).format(member=member)

        embed = discord.Embed(
            title="✨ New Member Alert! ✨",
            description=message,
            color=0x9B59B6
        )

        # Add member info
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Account Created", value=member.created_at.strftime("%B %d, %Y"), inline=True)
        embed.add_field(name="Member #", value=member.guild.member_count, inline=True)

        # Add some fun facts
        fun_facts = [
            f"Did you know? {member.guild.name} was created on {member.guild.created_at.strftime('%B %d, %Y')}!",
            f"Pro tip: Check out the rules in {self._rules_channel.mention if self._rules_channel else '#rules'}!",
            "Be sure to introduce yourself in the introductions channel!",
            "Don't forget to grab some roles to customize your experience!"
        ]

        embed.set_footer(text=random.choice(fun_facts))

        # Send the message
        await channel.send(embed=embed)

        # Add reactions
        message = await channel.send("Give them a warm welcome!")
        for emoji in ["👋", "🎉", "✨", "🌙"]:
            await message.add_reaction(emoji)

    async def _send_welcome_dm(self, member: discord.Member):
        """Send welcome DM to new member"""
        if not self._welcome_dms_enabled:
            return

        try:
            embed = discord.Embed(
                title=f"Welcome to {member.guild.name}!",
                description=(
                    f"Hello {member.mention}, and welcome to **{member.guild.name}**! "
                    "We're thrilled to have you join our magical community. "
                    "Here are a few things to help you get started:"
                ),
                color=0x9B59B6
            )

            # Add server info
            embed.add_field(
                name="📜 Server Rules",
                value=(
                    f"Please take a moment to review our server rules in "
                    f"{self._rules_channel.mention if self._rules_channel else 'the #rules channel'}. "
                    "They help keep our community welcoming and fun for everyone!"
                ),
                inline=False
            )

            # Add getting started tips
            embed.add_field(
                name="🚀 Getting Started",
                value=(
                    "- Introduce yourself in the introductions channel!\n"
                    "- Check out the roles channel to customize your experience.\n"
                    "- Don't be afraid to join conversations or ask questions!"
                ),
                inline=False
            )

            # Add support info
            embed.add_field(
                name="❓ Need Help?",
                value=(
                    "If you have any questions, feel free to ask our friendly staff members "
                    "or check out the FAQ channel for common questions."
                ),
                inline=False
            )

            embed.set_thumbnail(url=member.guild.icon.url if member.guild.icon else None)
            embed.set_footer(text="We're glad you're here!")

            await member.send(embed=embed)
        except discord.Forbidden:
            # Couldn't send DM (user has DMs disabled)
            pass

    async def _assign_welcome_roles(self, member: discord.Member):
        """Assign welcome roles to new member"""
        if not self._welcome_roles:
            return

        roles_to_add = []
        for role_id in self._welcome_roles:
            role = member.guild.get_role(role_id)
            if role and role not in member.roles:
                roles_to_add.append(role)

        if roles_to_add:
            try:
                await member.add_roles(*roles_to_add, reason="Welcome role assignment")
            except discord.Forbidden:
                pass  # Bot doesn't have permission to add roles

    async def _update_member_count(self, guild: discord.Guild):
        """Update member count in the member count channel"""
        if not self._member_count_channel:
            return

        channel = guild.get_channel(int(self._member_count_channel))
        if not channel:
            return

        # Get member count
        bot_count = sum(1 for member in guild.members if member.bot)
        human_count = guild.member_count - bot_count

        # Update channel name
        try:
            await channel.edit(name=f"👥 Members: {human_count:,}")
        except discord.Forbidden:
            pass  # Bot doesn't have permission to edit channel

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Handle new member joining"""
        # Run welcome tasks concurrently
        tasks = [
            self._assign_welcome_roles(member),
            self._send_welcome_message(member),
            self._send_welcome_dm(member),
            self._update_member_count(member.guild)
        ]
        await asyncio.gather(*tasks)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Handle member leaving"""
        # Send farewell message
        if self._welcome_channel and self._welcome_messages_enabled:
            channel = member.guild.get_channel(int(self._welcome_channel))
            if channel:
                message = random.choice(self.farewell_messages).format(member=member)
                await channel.send(f"**{message}**")

        # Update member count
        await self._update_member_count(member.guild)

    @commands.hybrid_command()
    @CovenTools.is_warlock()
    @app_commands.describe(channel="The channel to set as welcome channel")
    async def setwelcomechannel(self, ctx, channel: discord.TextChannel):
        """Set the welcome channel (Warlocks only)"""
        self._welcome_channel = str(channel.id)
        await self.bot.db.set_setting("welcome_channel", self._welcome_channel)
        await ctx.send(f"✅ Welcome channel set to {channel.mention}", ephemeral=True)

    @commands.hybrid_command()
    @CovenTools.is_warlock()
    @app_commands.describe(channel="The channel containing the rules")
    async def setruleschannel(self, ctx, channel: discord.TextChannel):
        """Set the rules channel (Warlocks only)"""
        self._rules_channel = channel
        await self.bot.db.set_setting("rules_channel", str(channel.id))
        await ctx.send(f"✅ Rules channel set to {channel.mention}", ephemeral=True)

    @commands.hybrid_command()
    @CovenTools.is_warlock()
    @app_commands.describe(channel="The channel to update with member count")
    async def setmembercountchannel(self, ctx, channel: discord.VoiceChannel):
        """Set the member count channel (Warlocks only)"""
        self._member_count_channel = str(channel.id)
        await self.bot.db.set_setting("member_count_channel", self._member_count_channel)
        await self._update_member_count(ctx.guild)
        await ctx.send(f"✅ Member count channel set to {channel.mention}", ephemeral=True)

    @commands.hybrid_command()
    @CovenTools.is_warlock()
    @app_commands.describe(role="Role to add as welcome role")
    async def addwelcomerole(self, ctx, role: discord.Role):
        """Add a welcome role (Warlocks only)"""
        if role.id in self._welcome_roles:
            return await ctx.send("❌ This role is already a welcome role.", ephemeral=True)

        self._welcome_roles.add(role.id)
        await self.bot.db.add_welcome_role(role.id)
        await ctx.send(f"✅ Added {role.mention} as a welcome role", ephemeral=True)

    @commands.hybrid_command()
    @CovenTools.is_warlock()
    @app_commands.describe(role="Role to remove from welcome roles")
    async def removewelcomerole(self, ctx, role: discord.Role):
        """Remove a welcome role (Warlocks only)"""
        if role.id not in self._welcome_roles:
            return await ctx.send("❌ This role is not a welcome role.", ephemeral=True)

        self._welcome_roles.remove(role.id)
        await self.bot.db.remove_welcome_role(role.id)
        await ctx.send(f"✅ Removed {role.mention} from welcome roles", ephemeral=True)

    @commands.hybrid_command()
    @CovenTools.is_warlock()
    async def listwelcomeroles(self, ctx):
        """List all welcome roles (Warlocks only)"""
        if not self._welcome_roles:
            return await ctx.send("No welcome roles set up yet.", ephemeral=True)

        roles = [ctx.guild.get_role(role_id) for role_id in self._welcome_roles]
        roles = [role.mention for role in roles if role]

        if not roles:
            return await ctx.send("No valid welcome roles found.", ephemeral=True)

        embed = discord.Embed(
            title="Welcome Roles",
            description="\n".join(roles) or "No roles found",
            color=0x9B59B6
        )

        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command()
    @CovenTools.is_warlock()
    @app_commands.describe(enabled="Whether to enable welcome DMs")
    async def togglewelcomedms(self, ctx, enabled: bool):
        """Enable or disable welcome DMs (Warlocks only)"""
        self._welcome_dms_enabled = enabled
        await self.bot.db.set_setting("welcome_dms_enabled", str(enabled))
        status = "enabled" if enabled else "disabled"
        await ctx.send(f"✅ Welcome DMs have been {status}", ephemeral=True)

    @commands.hybrid_command()
    @CovenTools.is_warlock()
    @app_commands.describe(enabled="Whether to enable welcome messages")
    async def togglewelcomemessages(self, ctx, enabled: bool):
        """Enable or disable welcome messages (Warlocks only)"""
        self._welcome_messages_enabled = enabled
        await self.bot.db.set_setting("welcome_messages_enabled", str(enabled))
        status = "enabled" if enabled else "disabled"
        await ctx.send(f"✅ Welcome messages have been {status}", ephemeral=True)

    @commands.hybrid_command()
    async def rules(self, ctx):
        """View the server rules"""
        embed = discord.Embed(
            title=f"📜 {ctx.guild.name} Rules",
            description="\n\n".join(self.rules),
            color=0x9B59B6
        )

        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)

        embed.set_footer(text="By being a member of this server, you agree to follow these rules.")

        await ctx.send(embed=embed)

    @commands.hybrid_command()
    async def faq(self, ctx, question: Optional[str] = None):
        """View frequently asked questions"""
        if not question:
            # Show all FAQs
            embed = discord.Embed(
                title="❓ Frequently Asked Questions",
                description="Use `/faq <question>` to get more information about a specific question.",
                color=0x9B59B6
            )

            for q, a in self.faq.items():
                embed.add_field(
                    name=f"❔ {q}",
                    value=a,
                    inline=False
                )

            await ctx.send(embed=embed)
        else:
            # Show specific FAQ
            question_lower = question.lower()
            for q, a in self.faq.items():
                if question_lower in q.lower():
                    embed = discord.Embed(
                        title=f"❓ {q}",
                        description=a,
                        color=0x9B59B6
                    )
                    return await ctx.send(embed=embed)

            await ctx.send("❌ Question not found. Use `/faq` to see all available questions.", ephemeral=True)

    @commands.hybrid_command()
    async def serverinfo(self, ctx):
        """Get information about the server"""
        guild = ctx.guild

        # Get member stats
        total_members = guild.member_count
        bot_count = sum(1 for member in guild.members if member.bot)
        human_count = total_members - bot_count
        online_members = sum(1 for member in guild.members if member.status != discord.Status.offline and not member.bot)

        # Get channel stats
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)

        # Get role stats
        role_count = len(guild.roles)

        # Get server creation date
        created_at = guild.created_at.strftime("%B %d, %Y")
        days_old = (datetime.utcnow() - guild.created_at).days

        # Create embed
        embed = discord.Embed(
            title=f"ℹ️ {guild.name} Server Info",
            color=0x9B59B6
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        # Server Info
        embed.add_field(
            name="📋 General",
            value=(
                f"**Owner:** {guild.owner.mention if guild.owner else 'Unknown'}\n"
                f"**Created:** {created_at} ({days_old} days ago)\n"
                f"**Region:** {str(guild.region).title()}\n"
                f"**Verification Level:** {str(guild.verification_level).title()}"
            ),
            inline=False
        )

        # Member Stats
        embed.add_field(
            name="👥 Members",
            value=(
                f"Total: {total_members:,}\n"
                f"Humans: {human_count:,}\n"
                f"Bots: {bot_count:,}\n"
                f"Online: {online_members:,}"
            ),
            inline=True
        )

        # Channel Stats
        embed.add_field(
            name="📚 Channels",
            value=(
                f"Text: {text_channels}\n"
                f"Voice: {voice_channels}\n"
                f"Categories: {categories}\n"
                f"Roles: {role_count}"
            ),
            inline=True
        )

        # Server Features
        if guild.features:
            features = [f"`{feature.replace('_', ' ').title()}`" for feature in guild.features]
            embed.add_field(
                name="✨ Features",
                value=", ".join(features) or "None",
                inline=False
            )

        # Server Boost Status
        if guild.premium_tier != 0:
            boosters = len(guild.premium_subscribers)
            boost_tier = f"Tier {guild.premium_tier}"
            boost_count = f"{guild.premium_subscription_count} boosts"

            embed.add_field(
                name="💎 Server Boost Status",
                value=f"Level: {boost_tier}\nBoosts: {boost_count}\nBoosters: {boosters}",
                inline=False
            )

        embed.set_footer(text=f"Server ID: {guild.id}")

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Onboarding(bot))
