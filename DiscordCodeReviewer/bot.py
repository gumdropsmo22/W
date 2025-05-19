from discord import app_commands
import os
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
import openai
import traceback
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('wilhelmina.log')
    ]
)
log = logging.getLogger('bot')

# Load environment variables
load_dotenv()

# Configure OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

async def get_prefix(_bot, _message):
    """Dynamic prefix handler (now properly scoped)"""
    # Per-guild override example (uncomment to enable later):
    # if message.guild:
    #     return guild_prefixes.get(message.guild.id, os.getenv('DEFAULT_PREFIX', '!'))
    return os.getenv('DEFAULT_PREFIX', '!')

class WilhelminaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        intents.message_content = True  

        super().__init__(
            command_prefix=get_prefix,
            intents=intents,
            help_command=None,
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="your whispers"
            )
        )
        self.initial_extensions = [
            'cogs.economy',
            'cogs.onboarding',
            'cogs.scheduler',
            'cogs.permissions',
            'cogs.music',
            'cogs.tarot',
            'cogs.sass',
            'cogs.moderation',
            'cogs.admin'
        ]
        self.config = self.load_config()

    @staticmethod
    def load_config():
        """Load configuration from environment variables"""
        class Config:
            pass

        config = Config()

        # Load config values
        config.AUTO_ROLE_ID = os.getenv('AUTO_ROLE_ID')
        config.ADMIN_ROLE_IDS = [int(id) for id in os.getenv('ADMIN_ROLE_IDS', '').split(',') if id.strip().isdigit()]

        return config

    async def setup_hook(self):
        """Setup the bot, called when the bot is starting"""
        # Load all extensions
        for extension in self.initial_extensions:
            try:
                await self.load_extension(extension)
                log.info(f"✅ Loaded {extension}")
            except Exception as e:
                log.error(f"❌ Failed to load {extension}: {type(e).__name__}: {e}")
                if isinstance(e, commands.ExtensionFailed):
                    log.error(f"Extension error: {e.original}")

        # Sync application commands
        await self.tree.sync()
        log.info("🔮 Bot is ready to serve")

    async def on_ready(self):
        """Verified startup sequence"""
        if not hasattr(self, 'uptime'):
            self.uptime = discord.utils.utcnow()

        if self.user:
            log.info(f'⚡ Logged in as {self.user} (ID: {self.user.id})')
            log.info(f'🔗 Invite: https://discord.com/oauth2/authorize?client_id={self.user.id}&permissions=2147485696&scope=bot%20applications.commands')
            log.info(f'🛠️ Loaded {len(self.cogs)} cogs: {", ".join(self.cogs.keys())}')
        else:
            log.error("Bot connected but user is None")

    async def close(self):
        """Clean shutdown handler"""
        await super().close()
        log.info("🔌 Bot disconnected gracefully")

# Create bot instance
bot = WilhelminaBot()

# Global commands
@bot.hybrid_command(name='help')
async def help_command(ctx):
    """Display help information about Wilhelmina"""
    prefix = ctx.prefix if ctx.prefix != ' ' else '!'

    embed = discord.Embed(
        title="🔮 Wilhelmina's Grimoire",
        description="Welcome to my coven, darling. Here are my mystical powers:",
        color=0x8A2BE2
    )

    # General Commands
    embed.add_field(
        name="🧙‍♀️ General",
        value=(
            f"`{prefix}help` - Display this grimoire\n"
            f"`{prefix}ask <question>` - Ask me anything\n"
            f"`{prefix}sass [user]` - Taste my witty venom\n"
            f"`{prefix}myrank` - See your standing in the coven"
        ),
        inline=False
    )

    # Tarot Commands
    embed.add_field(
        name="🔮 Divination",
        value=(
            f"`{prefix}tarot [spread]` - Get a tarot reading\n"
            f"`{prefix}tarotcard` - Draw a single card\n"
            f"`{prefix}imagine <prompt>` - Generate a magical image"
        ),
        inline=False
    )

    # Music Commands
    embed.add_field(
        name="🎵 Melody Magic",
        value=(
            f"`{prefix}play <song>` - Channel musical spirits\n"
            f"`{prefix}skip` - Banish the current song\n"
            f"`{prefix}queue` - View the musical ritual queue"
        ),
        inline=False
    )

    # Check for staff role (simplifying since we can't rely on coven_tools yet)
    # This will be properly implemented once the bot is fully loaded
    if ctx.author.guild_permissions.administrator:
        embed.add_field(
            name="⚖️ Elder Powers",
            value=(
                f"`{prefix}warn <user> <reason>` - Issue a formal warning\n"
                f"`{prefix}mute <user> [duration]` - Silence a troublemaker\n"
                f"`{prefix}purge <amount>` - Vanish messages into the void\n"
                f"`{prefix}setup` - Prepare the coven's sanctuary"
            ),
            inline=False
        )

    embed.set_footer(text="All commands work as slash (/) commands too | Made with 🖤")
    await ctx.send(embed=embed)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    """Handle errors for slash commands"""
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message(
            "🔒 You don't have permission to use this command.",
            ephemeral=True
        )
    elif isinstance(error, app_commands.errors.CommandOnCooldown):
        await interaction.response.send_message(
            f"⏳ Please wait {error.retry_after:.1f} seconds before using this command again.",
            ephemeral=True
        )
    else:
        log.error(f"Command error: {error}", exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "🔮 Something went wrong. The high priestess has been notified.",
                ephemeral=True
            )

def run_bot():
    """Start the Discord bot - callable from other modules"""
    try:
        # Check if token is provided
        token = os.getenv("DISCORD_TOKEN", "")
        if not token:
            log.critical("No Discord token provided. Please check your .env file.")
            return

        # Run the bot
        bot.run(token)
    except discord.LoginFailure:
        log.critical("Invalid token provided. Please check your .env file.")
        sys.exit(1)
    except Exception as e:
        log.critical(f"Failed to start bot: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    # Start the bot directly if script is run
    run_bot()
