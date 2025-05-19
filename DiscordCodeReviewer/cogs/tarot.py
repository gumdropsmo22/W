from typing import Tuple, List, Dict
import discord
import random
import logging
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta

# Initialize logging
log = logging.getLogger(__name__)

# Tarot card definitions
TAROT_CARDS = {
    "major": [
        {"name": "The Fool", "keywords": "beginnings, innocence, spontaneity", "image": "🃏"},
        {"name": "The Magician", "keywords": "manifestation, resourcefulness, power", "image": "✨"},
        {"name": "The High Priestess", "keywords": "intuition, sacred knowledge, divine feminine", "image": "🌙"},
        {"name": "The Empress", "keywords": "femininity, beauty, nature, abundance", "image": "👑"},
        {"name": "The Emperor", "keywords": "authority, structure, control, fatherhood", "image": "👑"},
        {"name": "The Hierophant", "keywords": "spiritual wisdom, tradition, conformity", "image": "🔮"},
        {"name": "The Lovers", "keywords": "partnerships, duality, union", "image": "❤️"},
        {"name": "The Chariot", "keywords": "direction, control, willpower", "image": "🏇"},
        {"name": "Strength", "keywords": "courage, patience, control, compassion", "image": "🦁"},
        {"name": "The Hermit", "keywords": "contemplation, search for truth, inner guidance", "image": "🏮"},
        {"name": "Wheel of Fortune", "keywords": "change, cycles, fate, destiny", "image": "🎡"},
        {"name": "Justice", "keywords": "fairness, truth, law, cause and effect", "image": "⚖️"},
        {"name": "The Hanged Man", "keywords": "sacrifice, release, martyrdom", "image": "🙃"},
        {"name": "Death", "keywords": "endings, change, transformation, transition", "image": "💀"},
        {"name": "Temperance", "keywords": "middle path, patience, finding meaning", "image": "🔄"},
        {"name": "The Devil", "keywords": "shadow self, attachment, addiction, restriction", "image": "😈"},
        {"name": "The Tower", "keywords": "sudden change, upheaval, revelation, awakening", "image": "🗼"},
        {"name": "The Star", "keywords": "hope, faith, purpose, renewal, spirituality", "image": "⭐"},
        {"name": "The Moon", "keywords": "illusion, fear, anxiety, subconscious", "image": "🌕"},
        {"name": "The Sun", "keywords": "joy, success, celebration, positivity", "image": "☀️"},
        {"name": "Judgment", "keywords": "reflection, reckoning, awakening", "image": "📯"},
        {"name": "The World", "keywords": "completion, integration, accomplishment, travel", "image": "🌍"}
    ],
    "cups": [
        {"name": "Ace of Cups", "keywords": "new feelings, intuition, intimacy", "image": "🏆"},
        {"name": "Two of Cups", "keywords": "unified love, partnership, mutual attraction", "image": "🏆"},
        {"name": "Three of Cups", "keywords": "friendship, community, happiness", "image": "🏆"},
        {"name": "Four of Cups", "keywords": "apathy, contemplation, disconnectedness", "image": "🏆"},
        {"name": "Five of Cups", "keywords": "loss, grief, self-pity", "image": "🏆"},
        {"name": "Six of Cups", "keywords": "familiarity, happy memories, healing", "image": "🏆"},
        {"name": "Seven of Cups", "keywords": "choices, fantasy, illusion", "image": "🏆"},
        {"name": "Eight of Cups", "keywords": "walking away, disillusionment", "image": "🏆"},
        {"name": "Nine of Cups", "keywords": "contentment, satisfaction, gratitude", "image": "🏆"},
        {"name": "Ten of Cups", "keywords": "divine love, blissful relationships, harmony", "image": "🏆"},
        {"name": "Page of Cups", "keywords": "creative opportunities, curiosity, possibility", "image": "🏆"},
        {"name": "Knight of Cups", "keywords": "following the heart, idealist, romantic", "image": "🏆"},
        {"name": "Queen of Cups", "keywords": "compassion, calm, comfort", "image": "🏆"},
        {"name": "King of Cups", "keywords": "emotional balance, generosity", "image": "🏆"}
    ],
    "pentacles": [
        {"name": "Ace of Pentacles", "keywords": "opportunity, prosperity, new venture", "image": "💰"},
        {"name": "Two of Pentacles", "keywords": "balancing decisions, priorities, adaptation", "image": "💰"},
        {"name": "Three of Pentacles", "keywords": "teamwork, collaboration, learning", "image": "💰"},
        {"name": "Four of Pentacles", "keywords": "conservation, frugality, security", "image": "💰"},
        {"name": "Five of Pentacles", "keywords": "need, poverty, insecurity", "image": "💰"},
        {"name": "Six of Pentacles", "keywords": "charity, generosity, sharing", "image": "💰"},
        {"name": "Seven of Pentacles", "keywords": "harvest, rewards, patience", "image": "💰"},
        {"name": "Eight of Pentacles", "keywords": "diligence, knowledge, detail", "image": "💰"},
        {"name": "Nine of Pentacles", "keywords": "fruits of labor, luxury, self-sufficiency", "image": "💰"},
        {"name": "Ten of Pentacles", "keywords": "legacy, inheritance, establishment", "image": "💰"},
        {"name": "Page of Pentacles", "keywords": "ambition, desire, diligence", "image": "💰"},
        {"name": "Knight of Pentacles", "keywords": "efficiency, hard work, responsibility", "image": "💰"},
        {"name": "Queen of Pentacles", "keywords": "practicality, creature comforts, security", "image": "💰"},
        {"name": "King of Pentacles", "keywords": "abundance, prosperity, security", "image": "💰"}
    ],
        "swords": [
        {"name": "Ace of Swords", "keywords": "breakthrough, clarity, sharp mind", "image": "⚔️"},
        {"name": "Two of Swords", "keywords": "difficult choices, indecision, stalemate", "image": "⚔️"},
        {"name": "Three of Swords", "keywords": "heartbreak, suffering, grief", "image": "⚔️"},
        {"name": "Four of Swords", "keywords": "rest, restoration, contemplation", "image": "⚔️"},
        {"name": "Five of Swords", "keywords": "conflict, tension, loss", "image": "⚔️"},
        {"name": "Six of Swords", "keywords": "transition, leaving behind, moving on", "image": "⚔️"},
        {"name": "Seven of Swords", "keywords": "deception, trickery, tactics", "image": "⚔️"},
        {"name": "Eight of Swords", "keywords": "imprisonment, entrapment, self-victimization", "image": "⚔️"},
        {"name": "Nine of Swords", "keywords": "anxiety, worry, fear", "image": "⚔️"},
        {"name": "Ten of Swords", "keywords": "failure, collapse, defeat", "image": "⚔️"},
        {"name": "Page of Swords", "keywords": "curiosity, restlessness, mental energy", "image": "⚔️"},
        {"name": "Knight of Swords", "keywords": "action, impulsiveness, defending beliefs", "image": "⚔️"},
        {"name": "Queen of Swords", "keywords": "complexity, perceptiveness, clear mindedness", "image": "⚔️"},
        {"name": "King of Swords", "keywords": "head over heart, discipline, truth", "image": "⚔️"}
    ],
    "wands": [
        {"name": "Ace of Wands", "keywords": "creation, willpower, inspiration, desire", "image": "🔥"},
        {"name": "Two of Wands", "keywords": "planning, making decisions, leaving home", "image": "🔥"},
        {"name": "Three of Wands", "keywords": "looking ahead, expansion, rapid growth", "image": "🔥"},
        {"name": "Four of Wands", "keywords": "community, home, celebrations", "image": "🔥"},
        {"name": "Five of Wands", "keywords": "competition, conflict, diversity", "image": "🔥"},
        {"name": "Six of Wands", "keywords": "victory, success, public reward", "image": "🔥"},
        {"name": "Seven of Wands", "keywords": "perseverance, defensive, maintaining control", "image": "🔥"},
        {"name": "Eight of Wands", "keywords": "rapid action, movement, quick decisions", "image": "🔥"},
        {"name": "Nine of Wands", "keywords": "resilience, grit, last stand", "image": "🔥"},
        {"name": "Ten of Wands", "keywords": "accomplishment, responsibility, burden", "image": "🔥"},
        {"name": "Page of Wands", "keywords": "exploration, excitement, freedom", "image": "🔥"},
        {"name": "Knight of Wands", "keywords": "energy, passion, adventure", "image": "🔥"},
        {"name": "Queen of Wands", "keywords": "courage, determination, joy", "image": "🔥"},
        {"name": "King of Wands", "keywords": "big picture, leader, overcoming challenges", "image": "🔥"}
    ]
}

class TarotSpreadView(discord.ui.View):
    def __init__(self, ctx, cards, spread_type):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.cards = cards
        self.spread_type = spread_type
        self.current_card = 0
        self.expanded = False

    @discord.ui.button(label="Next Card", style=discord.ButtonStyle.primary, emoji="➡️")
    async def next_card(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message(
                "This reading isn't for you, dear one.",
                ephemeral=True
            )

        self.current_card += 1
        if self.current_card >= len(self.cards):
            self.current_card = 0

        await self._update_embed(interaction)

    @discord.ui.button(label="Previous Card", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def prev_card(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message(
                "This reading isn't for you, dear one.",
                ephemeral=True
            )

        self.current_card -= 1
        if self.current_card < 0:
            self.current_card = len(self.cards) - 1

        await self._update_embed(interaction)

    @discord.ui.button(label="Expand Reading", style=discord.ButtonStyle.success, emoji="🔍")
    async def expand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message(
                "This reading isn't for you, dear one.",
                ephemeral=True
            )

        self.expanded = not self.expanded
        button.label = "Show Cards" if self.expanded else "Expand Reading"
        await self._update_embed(interaction)

    async def _update_embed(self, interaction: discord.Interaction):
        if self.expanded:
            embed = self._create_full_spread_embed()
        else:
            card = self.cards[self.current_card]
            embed = self._create_card_embed(
                card, 
                f"Card {self.current_card + 1} of {len(self.cards)}"
            )
        await interaction.response.edit_message(embed=embed, view=self)

    @staticmethod
    def _create_card_embed(card, subtitle=None):
        is_reversed = card.get("reversed", False)
        card_name = f"{card['name']} (Reversed)" if is_reversed else card['name']

        embed = discord.Embed(
            title=f"{card['image']} {card_name}",
            color=0x8A2BE2
        )

        if subtitle:
            embed.description = f"*{subtitle}*"

        if is_reversed:
            embed.add_field(
                name="Meaning (Reversed)",
                value=f"Keywords: {card['keywords_reversed'] if 'keywords_reversed' in card else 'Blocked ' + card['keywords']}",
                inline=False
            )
        else:
            embed.add_field(
                name="Meaning",
                value=f"Keywords: {card['keywords']}",
                inline=False
            )

        if "interpretation" in card:
            embed.add_field(
                name="Reading",
                value=card["interpretation"],
                inline=False
            )

        return embed

    def _create_full_spread_embed(self):
        spread_name = {
            "single": "Single Card",
            "three": "Past-Present-Future",
            "celtic": "Celtic Cross"
        }.get(self.spread_type, "Tarot Spread")

        embed = discord.Embed(
            title=f"🔮 {spread_name} Reading for {self.ctx.author.display_name}",
            color=0x8A2BE2,
            timestamp=datetime.utcnow()
        )

        if self.spread_type == "single":
            card = self.cards[0]
            is_reversed = card.get("reversed", False)
            status = " (Reversed)" if is_reversed else ""
            embed.add_field(
                name=f"{card.get('image', '')} {card.get('name', 'Unknown')}{status}",
                value=(
                    f"**Keywords:** {card.get('keywords', 'N/A')}\n"
                    f"**Reading:** {card.get('interpretation', 'No interpretation available')}"
                ),
                inline=False
            )

        elif self.spread_type == "three":
            positions = ["Past", "Present", "Future"]
            for i, card in enumerate(self.cards):
                is_reversed = card.get("reversed", False)
                status = " (Reversed)" if is_reversed else ""
                embed.add_field(
                    name=f"{positions[i]}: {card.get('image', '')} {card.get('name', 'Unknown')}{status}",
                    value=(
                        f"**Keywords:** {card.get('keywords', 'N/A')}\n"
                        f"**Reading:** {card.get('interpretation', 'No interpretation available')}"
                    ),
                    inline=False
                )

        elif self.spread_type == "celtic":
            positions = [
                "Present", "Challenge", "Subconscious", "Past", "Crown", "Future",
                "Self", "Environment", "Hopes/Fears", "Outcome"
            ]

            # First 6 cards in the cross
            for i in range(min(6, len(self.cards))):
                card = self.cards[i]
                is_reversed = card.get("reversed", False)
                status = " (Reversed)" if is_reversed else ""
                embed.add_field(
                    name=f"{positions[i]}: {card['image']} {card['name']}{status}",
                    value=f"**Keywords:** {card['keywords']}\n**Reading:** {card.get('interpretation', '...')}",
                    inline=(i >= 2)
                )

            # Additional cards in the staff
            if len(self.cards) > 6:
                embed.add_field(name="\u200b", value="**The Staff**", inline=False)

                for i in range(6, min(10, len(self.cards))):
                    card = self.cards[i]
                    is_reversed = card.get("reversed", False)
                    status = " (Reversed)" if is_reversed else ""
                    embed.add_field(
                        name=f"{positions[i]}: {card['image']} {card['name']}{status}",
                        value=f"**Keywords:** {card['keywords']}\n**Reading:** {card.get('interpretation', '...')}",
                        inline=True
                    )

        embed.set_footer(text="May the cards illuminate your path... or not.")
        return embed

class Tarot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reading_cooldowns = {}
        self.card_cache = {}
        self.TAROT_COOLDOWN = 3600  # 1 hour cooldown in seconds

    def _get_cooldown(self, user_id: int) -> int:
        last_time = self.reading_cooldowns.get(user_id, 0)
        cooldown = max(0, self.TAROT_COOLDOWN - (discord.utils.utcnow().timestamp() - last_time))
        return int(cooldown)

    @staticmethod
    def _draw_cards(count: int) -> List[Dict]:
        all_cards = []
        for _, cards in TAROT_CARDS.items():
            all_cards.extend(cards)

        drawn = random.sample(all_cards, count)
        for card in drawn:
            card = card.copy()
            card["reversed"] = random.random() < 0.2
        return drawn

    @staticmethod
    async def _generate_interpretations(cards: List[Dict], spread_type: str, user: discord.User) -> List[Dict]:
        cards_with_interpretations = [card.copy() for card in cards]

        # Simulate AI interpretation (replace with actual AI call)
        for card in cards_with_interpretations:
            if card.get("reversed", False):
                card["interpretation"] = f"The reversed {card['name']} suggests blocked or inverted energy of {card['keywords']}."
            else:
                card["interpretation"] = f"The {card['name']} brings the energy of {card['keywords']} into your life."

        return cards_with_interpretations

    async def _prepare_reading(self, user: discord.User, spread: str) -> Tuple[List[Dict], bool]:
        user_cache = self.card_cache.get(user.id, {})
        spread_cache = user_cache.get(spread, None)

        if spread_cache and (datetime.utcnow() - spread_cache["timestamp"]) < timedelta(minutes=10):
            return spread_cache["cards"], True

        if spread == "single":
            count = 1
        elif spread == "three":
            count = 3
        elif spread == "celtic":
            count = 10
        else:
            count = 1

        cards = self._draw_cards(count)
        cards_with_interpretations = await self._generate_interpretations(cards, spread, user)

        if user.id not in self.card_cache:
            self.card_cache[user.id] = {}

        self.card_cache[user.id][spread] = {
            "cards": cards_with_interpretations,
            "timestamp": datetime.utcnow()
        }

        return cards_with_interpretations, False

    @commands.hybrid_command()
    @app_commands.describe(spread="Type of spread (single, three, celtic)")
    async def tarot(self, ctx: commands.Context, spread: str = "single"):
        """Get a mystical tarot reading"""
        spread = spread.lower()
        if spread not in {"single", "three", "celtic"}:
            return await ctx.send(
                "🔮 Valid spreads are: single, three, celtic",
                ephemeral=True
            )

        remaining = self._get_cooldown(ctx.author.id)
        if remaining > 0:
            minutes = remaining // 60
            seconds = remaining % 60
            return await ctx.send(
                f"⏳ The cards need {minutes}m {seconds}s more to recharge for you.",
                ephemeral=True
            )

        self.reading_cooldowns[ctx.author.id] = discord.utils.utcnow().timestamp()

        async with ctx.typing():
            cards, _ = await self._prepare_reading(ctx.author, spread)

        # For single card display
        first_card = cards[0]
        is_reversed = first_card.get("reversed", False)
        card_name = f"{first_card['name']} (Reversed)" if is_reversed else first_card['name']

        embed = discord.Embed(
            title=f"🔮 Tarot Reading for {ctx.author.display_name}",
            description="*The cards have spoken...*",
            color=0x8A2BE2
        )
        embed.add_field(
            name=f"{first_card['image']} {card_name}",
            value=f"Keywords: {first_card['keywords']}",
            inline=False
        )

        if "interpretation" in first_card:
            embed.add_field(
                name="Interpretation",
                value=first_card["interpretation"],
                inline=False
            )

        if len(cards) > 1:
            embed.set_footer(text=f"Card 1 of {len(cards)} • Use the buttons to navigate")
            view = TarotSpreadView(ctx, cards, spread)
            await ctx.send(embed=embed, view=view)
        else:
            embed.set_footer(text="May the cards illuminate your path... or not.")
            await ctx.send(embed=embed)

    @commands.hybrid_command()
    async def tarotcard(self, ctx: commands.Context):
        """Draw a single tarot card"""
        await self.tarot(ctx, spread="single")

    @commands.hybrid_command()
    @app_commands.describe(question="Your question for the tarot cards")
    async def asktarot(self, ctx: commands.Context, *, question: str):
        """Ask a specific question to the tarot cards"""
        remaining = self._get_cooldown(ctx.author.id)
        if remaining > 0:
            minutes = remaining // 60
            seconds = remaining % 60
            return await ctx.send(
                f"⏳ The cards need {minutes}m {seconds}s more to recharge for you.",
                ephemeral=True
            )

        self.reading_cooldowns[ctx.author.id] = discord.utils.utcnow().timestamp()

        async with ctx.typing():
            cards = self._draw_cards(3)
            cards_with_interpretations = await self._generate_interpretations(cards, "question", ctx.author)

            embed = discord.Embed(
                title="🔮 Tarot Answer",
                description=f"*Question: {question}*",
                color=0x8A2BE2
            )

            positions = ["Influence", "Challenge", "Outcome"]
            for i, card in enumerate(cards_with_interpretations):
                is_reversed = card.get("reversed", False)
                card_name = f"{card['image']} {card['name']} (Reversed)" if is_reversed else f"{card['image']} {card['name']}"
                embed.add_field(
                    name=f"{positions[i]}: {card_name}",
                    value=card["interpretation"],
                    inline=False
                )

            embed.set_footer(text="The future is fluid, like the tears of your enemies...")
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Tarot(bot))




























