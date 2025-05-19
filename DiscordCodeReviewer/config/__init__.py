import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Helper to cast environment variables to int with a default
def env_int(key, default=0):
    return int(os.getenv(key, default))

# Discord configuration
TOKEN = os.getenv("DISCORD_TOKEN")
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")

# Role IDs
WARLOCK_ROLE_ID = env_int("WARLOCK_ROLE_ID")
AUTO_ROLE_ID = env_int("AUTO_ROLE_ID")

# Channel IDs
TEA_CHANNEL_ID = env_int("TEA_CHANNEL_ID")
TAROT_CHANNEL_ID = env_int("TAROT_CHANNEL_ID")
ARCHIVE_CATEGORY_ID = env_int("ARCHIVE_CATEGORY_ID")
MOD_LOG_CHANNEL_ID = env_int("MOD_LOG_CHANNEL_ID")

# Feature settings
MAX_IMAGES = env_int("MAX_IMAGES", 5)
TAROT_COOLDOWN = env_int("TAROT_COOLDOWN", 3600)

# OpenAI settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Exports
__all__ = [
    'TOKEN', 'COMMAND_PREFIX',
    'WARLOCK_ROLE_ID', 'AUTO_ROLE_ID',
    'TEA_CHANNEL_ID', 'TAROT_CHANNEL_ID', 'ARCHIVE_CATEGORY_ID', 'MOD_LOG_CHANNEL_ID',
    'MAX_IMAGES', 'TAROT_COOLDOWN', 'OPENAI_API_KEY'
]
