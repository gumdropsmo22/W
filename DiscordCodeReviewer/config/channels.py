from . import (
    TEA_CHANNEL_ID,
    TAROT_CHANNEL_ID,
    ARCHIVE_CATEGORY_ID
)

# Channel permission overwrites (default denies all)
BASE_OVERWRITES = {
    "read_messages": False,
    "send_messages": False,
    "add_reactions": False
}

CHANNEL_CONFIGS = {
    "tea_spillage": {
        "id": TEA_CHANNEL_ID,
        "type": "text",
        "overwrites": {
            **BASE_OVERWRITES,
            "read_messages": True,
            "send_messages": True,
            "embed_links": True
        },
        "slowmode": 5  # Seconds
    },
    "divination_den": {
        "id": TAROT_CHANNEL_ID,
        "type": "text",
        "overwrites": {
            **BASE_OVERWRITES,
            "read_messages": True,
            "send_messages": True,
            "attach_files": False
        },
        "topic": "🔮 Tarot readings only - Keep it mystical"
    },
    "archive_of_shame": {
        "id": ARCHIVE_CATEGORY_ID,
        "type": "category",
        "overwrites": {
            **BASE_OVERWRITES,
            "read_message_history": True
        },
        "nsfw": True,
        "locked": True  # No new messages allowed
    }
}
