import sqlite3
import discord
import asyncio
import aiosqlite
import random
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union, AsyncGenerator
from pathlib import Path
from contextlib import asynccontextmanager
from .. import CovenTools

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = Path("data/economy.db")
        self.db_path.parent.mkdir(exist_ok=True)
        self.currency_name = "crystals"
        self.currency_emoji = "💎"

        # Cache and locks
        self._balance_cache: Dict[int, int] = {}
        self._db_lock = asyncio.Lock()

        # Initialize database
        self.bot.loop.create_task(self._init_db())

    async def _init_db(self):
        """Initialize database tables if they don't exist"""
        async with self.get_db() as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS economy (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER DEFAULT 0,
                    last_daily TEXT,
                    lifetime_earned INTEGER DEFAULT 0
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS shop_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    description TEXT,
                    price INTEGER,
                    role_id INTEGER,
                    stock INTEGER DEFAULT -1,
                    max_per_user INTEGER DEFAULT 1
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_inventory (
                    user_id INTEGER,
                    item_id INTEGER,
                    quantity INTEGER DEFAULT 1,
                    purchased_at TEXT,
                    PRIMARY KEY (user_id, item_id)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount INTEGER,
                    type TEXT,
                    reference TEXT,
                    timestamp TEXT
                )
            """)

            # Add default items if shop is empty
            cursor = await db.execute("SELECT COUNT(*) FROM shop_items")
            if (await cursor.fetchone())[0] == 0:
                default_items = [
                    ("Custom Role", "A unique role just for you", 1000, None, -1, 1),
                    ("Color Change", "Change your role color", 500, None, -1, 5),
                    ("Name Change", "Change your display name", 300, None, -1, 3),
                    ("Exclusive Channel", "Access to exclusive channels", 2000, None, 50, 1)
                ]
                await db.executemany(
                    """INSERT INTO shop_items 
                    (name, description, price, role_id, stock, max_per_user) 
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    default_items
                )

            await db.commit()

    @asynccontextmanager
    async def get_db(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Async context manager for database connections"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    async def _get_balance(self, user_id: int) -> int:
        """Get user's balance with cache support"""
        if user_id in self._balance_cache:
            return self._balance_cache[user_id]

        async with self.get_db() as db:
            await db.execute(
                "INSERT OR IGNORE INTO economy (user_id, balance) VALUES (?, 0)",
                (user_id,)
            )
            cursor = await db.execute(
                "SELECT balance FROM economy WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            balance = row['balance'] if row else 0

        self._balance_cache[user_id] = balance
        return balance

    async def _update_balance(
        self,
        user_id: int,
        amount: int,
        transaction_type: str,
        reference: str = ""
    ) -> int:
        """Update user's balance atomically"""
        async with self._db_lock, self.get_db() as db:
            # Get current balance
            cursor = await db.execute(
                "SELECT balance, lifetime_earned FROM economy WHERE user_id = ?",
                (user_id,)
            )
            result = await cursor.fetchone()

            if not result:  # User doesn't exist yet
                new_balance = max(amount, 0)  # Prevent negative balance for new users
                lifetime = max(amount, 0)
                await db.execute(
                    "INSERT INTO economy (user_id, balance, lifetime_earned) VALUES (?, ?, ?)",
                    (user_id, new_balance, lifetime)
                )
            else:
                current_balance = result['balance']
                new_balance = max(current_balance + amount, 0)  # Prevent negative balance
                lifetime = result['lifetime_earned'] + max(amount, 0)

                # Update balance
                await db.execute(
                    """UPDATE economy 
                        SET balance = ?, 
                            lifetime_earned = ? 
                        WHERE user_id = ?""",
                    (new_balance, lifetime, user_id)
                )

            # Log transaction
            await db.execute(
                """INSERT INTO transactions 
                    (user_id, amount, type, reference, timestamp)
                    VALUES (?, ?, ?, ?, ?)""",
                (user_id, amount, transaction_type, reference, 
                 datetime.utcnow().isoformat())
            )

            # Update cache
            self._balance_cache[user_id] = new_balance
            return new_balance

    @commands.hybrid_command()
    async def balance(self, ctx, user: Optional[discord.Member] = None):
        """Check your or another user's crystal balance"""
        target = user or ctx.author
        balance = await self._get_balance(target.id)

        async with self.get_db() as db:
            # Get rank
            cursor = await db.execute("""
                SELECT COUNT(*) + 1 as rank 
                FROM economy 
                WHERE balance > (SELECT balance FROM economy WHERE user_id = ?)
            """, (target.id,))
            rank_row = await cursor.fetchone()
            rank = rank_row['rank'] if rank_row else 1

            # Get total users
            cursor = await db.execute("SELECT COUNT(*) as total FROM economy")
            total_users = (await cursor.fetchone())['total']

        embed = discord.Embed(
            title=f"{target.display_name}'s {self.currency_name.capitalize()}",
            color=0x9B59B6
        )

        embed.add_field(
            name="Balance", 
            value=f"{self.currency_emoji} **{balance:,}**", 
            inline=True
        )

        if total_users > 0:
            embed.add_field(
                name="Rank", 
                value=f"#{rank:,} of {total_users:,}", 
                inline=True
            )

        if target == ctx.author:
            embed.description = (
                f"Use `/daily` to claim your daily {self.currency_emoji}\n"
                f"Use `/work` to earn more {self.currency_emoji}"
            )

        await ctx.send(embed=embed)

    @commands.hybrid_command()
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def daily(self, ctx):
        """Claim your daily crystals"""
        amount = 100  # Base amount
        bonus = 0
        streak = 1

        async with self.get_db() as db:
            # Get last daily claim
            cursor = await db.execute(
                "SELECT last_daily FROM economy WHERE user_id = ?",
                (ctx.author.id,)
            )
            result = await cursor.fetchone()

            if result and result['last_daily']:
                last_daily = datetime.fromisoformat(result['last_daily'])
                now = datetime.utcnow()

                # Check if within streak window (36 hours)
                if (now - last_daily) < timedelta(hours=36):
                    # Calculate streak
                    cursor = await db.execute("""
                        SELECT COUNT(*) as streak 
                        FROM transactions 
                        WHERE user_id = ? 
                        AND type = 'daily' 
                        AND timestamp > ?
                    """, (ctx.author.id, (now - timedelta(days=7)).isoformat()))
                    streak = (await cursor.fetchone())['streak'] + 1
                    bonus = min(50 * streak, 200)  # Max 200 bonus
                    amount += bonus

                    if streak > 1:
                        title = f"🎉 Daily Reward (Day {streak})"
                        desc = f"You've received {amount} {self.currency_emoji} (Streak Bonus: {bonus} {self.currency_emoji})"
                        color = 0x2ECC71
                    else:
                        title = "🎉 Daily Reward"
                        desc = f"You've received {amount} {self.currency_emoji}"
                        color = 0x2ECC71
                else:
                    # Streak broken
                    title = "💔 Streak Broken"
                    desc = f"You've received {amount} {self.currency_emoji} (Streak reset)"
                    color = 0xE74C3C
            else:
                # First daily
                title = "🎉 First Daily Reward!"
                desc = f"You've received {amount} {self.currency_emoji}"
                color = 0x2ECC71

            # Update last_daily
            await db.execute(
                """INSERT OR REPLACE INTO economy 
                (user_id, last_daily) 
                VALUES (?, ?)""",
                (ctx.author.id, datetime.utcnow().isoformat())
            )

            # Add to balance
            new_balance = await self._update_balance(
                ctx.author.id, 
                amount, 
                "daily"
            )

        embed = discord.Embed(
            title=title,
            description=desc,
            color=color
        )
        embed.set_footer(text=f"New balance: {new_balance:,} {self.currency_emoji}")

        await ctx.send(embed=embed)

    @commands.hybrid_command()
    @commands.cooldown(1, 3600, commands.BucketType.user)
    async def work(self, ctx):
        """Work to earn crystals"""
        # Generate random amount between 10-50
        base_amount = random.randint(10, 50)

        # Apply role bonus
        if any(role.name.lower() in ["high priest", "high priestess"] 
              for role in ctx.author.roles):
            amount = int(base_amount * 1.5)
            bonus = amount - base_amount
        else:
            amount = base_amount
            bonus = 0

        # Add to balance
        new_balance = await self._update_balance(
            ctx.author.id, 
            amount, 
            "work"
        )

        # Create embed
        embed = discord.Embed(
            title="💼 Work Complete",
            description=(
                f"You earned {amount} {self.currency_emoji} "
                f"(+{bonus} {self.currency_emoji} role bonus)" if bonus else ""
            ).strip(),
            color=0x3498DB
        )
        embed.set_footer(text=f"New balance: {new_balance:,} {self.currency_emoji}")

        await ctx.send(embed=embed)

    @commands.hybrid_command()
    @app_commands.describe(amount="Amount to transfer", user="User to transfer to")
    async def pay(self, ctx, amount: int, user: discord.Member):
        """Transfer crystals to another user"""
        if amount <= 0:
            return await ctx.send("❌ Amount must be positive.", ephemeral=True)

        if user.bot:
            return await ctx.send("❌ Cannot transfer to bots.", ephemeral=True)

        if user.id == ctx.author.id:
            return await ctx.send("❌ Cannot transfer to yourself.", ephemeral=True)

        try:
            async with self._db_lock:  # Prevent race conditions
                # Verify sender has enough balance
                sender_balance = await self._get_balance(ctx.author.id)
                if sender_balance < amount:
                    return await ctx.send("❌ Insufficient balance.", ephemeral=True)

                # Perform transfer
                await self._update_balance(
                    ctx.author.id, 
                    -amount, 
                    "transfer_out", 
                    f"to:{user.id}"
                )
                await self._update_balance(
                    user.id, 
                    amount, 
                    "transfer_in", 
                    f"from:{ctx.author.id}"
                )

                # Get new balance
                new_balance = await self._get_balance(ctx.author.id)

                embed = discord.Embed(
                    title="💸 Transfer Complete",
                    description=(
                        f"You've sent {amount} {self.currency_emoji} to {user.mention}\n"
                        f"Your new balance: {new_balance:,} {self.currency_emoji}"
                    ),
                    color=0x2ECC71
                )
                await ctx.send(embed=embed)

        except Exception:
            await ctx.send("❌ An error occurred during the transfer.", ephemeral=True)
            raise

    @commands.hybrid_command()
    async def shop(self, ctx):
        """View the crystal shop"""
        async with self.get_db() as db:
            cursor = await db.execute("""
                SELECT 
                    id, name, description, price, 
                    stock, max_per_user 
                FROM shop_items 
                ORDER BY price
            """)
            items = await cursor.fetchall()

            if not items:
                return await ctx.send("The shop is currently empty.", ephemeral=True)

            embed = discord.Embed(
                title="🛍️ Crystal Shop",
                description="Use `/buy <item_id>` to purchase an item",
                color=0x9B59B6
            )

            for item in items:
                # Check how many the user already owns
                cursor = await db.execute("""
                    SELECT COALESCE(SUM(quantity), 0) as owned
                    FROM user_inventory 
                    WHERE user_id = ? AND item_id = ?
                """, (ctx.author.id, item['id']))
                owned = (await cursor.fetchone())['owned']

                # Build item info
                info = f"**Price:** {item['price']:,} {self.currency_emoji}\n"

                # Show stock info
                if item['stock'] > 0:
                    info += f"**In Stock:** {item['stock']:,}\n"
                elif item['stock'] == 0:
                    info += "**Out of Stock**\n"

                # Show ownership info
                if item['max_per_user'] > 0:
                    info += f"**Owned:** {owned}/{item['max_per_user']}\n"

                # Add description if available
                if item['description']:
                    info += f"\n{item['description']}"

                embed.add_field(
                    name=f"#{item['id']} - {item['name']}",
                    value=info,
                    inline=False
                )

            await ctx.send(embed=embed)

    @commands.hybrid_command()
    @app_commands.describe(item_id="ID of the item to buy")
    async def buy(self, ctx, item_id: int):
        """Purchase an item from the shop"""
        try:
            async with self._db_lock, self.get_db() as db:
                # Get item info
                cursor = await db.execute("""
                        SELECT * FROM shop_items WHERE id = ?
                    """, (item_id,))
                item = await cursor.fetchone()

                if not item:
                    return await ctx.send("❌ Item not found.", ephemeral=True)

                # Check stock
                if item['stock'] == 0:
                    return await ctx.send("❌ This item is out of stock.", ephemeral=True)

                # Check if user has reached purchase limit
                if item['max_per_user'] > 0:
                    cursor = await db.execute("""
                            SELECT COALESCE(SUM(quantity), 0) as owned
                            FROM user_inventory 
                            WHERE user_id = ? AND item_id = ?
                        """, (ctx.author.id, item_id))
                    owned = (await cursor.fetchone())['owned']

                    if owned >= item['max_per_user']:
                        return await ctx.send(
                            f"❌ You can only own {item['max_per_user']} of this item.",
                            ephemeral=True
                        )

                # Check balance
                balance = await self._get_balance(ctx.author.id)
                if balance < item['price']:
                    return await ctx.send(
                        f"❌ You need {item['price'] - balance} more {self.currency_emoji} to buy this!",
                        ephemeral=True
                    )

                # Deduct balance
                new_balance = await self._update_balance(
                    ctx.author.id,
                    -item['price'],
                    "purchase",
                    f"item:{item_id}"
                )

                # Add to inventory
                await db.execute("""
                        INSERT INTO user_inventory 
                        (user_id, item_id, quantity, purchased_at)
                        VALUES (?, ?, 1, ?)
                        ON CONFLICT(user_id, item_id) 
                        DO UPDATE SET 
                            quantity = quantity + 1,
                            purchased_at = ?
                    """, (
                    ctx.author.id, 
                    item_id, 
                    datetime.utcnow().isoformat(),
                    datetime.utcnow().isoformat()
                ))

                # Update stock if not unlimited
                if item['stock'] > 0:
                    await db.execute("""
                            UPDATE shop_items 
                            SET stock = stock - 1 
                            WHERE id = ? AND stock > 0
                        """, (item_id,))

                # Commit all changes
                await db.commit()

                # Handle role assignment if applicable
                if item['role_id']:
                    try:
                        role = ctx.guild.get_role(item['role_id'])
                        if role and role not in ctx.author.roles:
                            await ctx.author.add_roles(
                                role, 
                                reason=f"Purchased {item['name']}"
                            )
                            role_msg = f"\nYou've been given the {role.mention} role!"
                    except discord.Forbidden:
                        role_msg = "\n*Note: Could not assign role (missing permissions)*"
                    except Exception:
                        role_msg = "\n*Note: Could not assign role*"
                else:
                    role_msg = ""

                # Send success message
                embed = discord.Embed(
                    title="✅ Purchase Complete",
                    description=(
                        f"You've purchased **{item['name']}** for "
                        f"{item['price']:,} {self.currency_emoji}\n"
                        f"Your new balance: {new_balance:,} {self.currency_emoji}"
                        f"{role_msg}"
                    ),
                    color=0x2ECC71
                )
                await ctx.send(embed=embed)

        except Exception:
            await ctx.send("❌ An error occurred while processing your purchase.", ephemeral=True)
            raise

    @commands.hybrid_command()
    async def inventory(self, ctx, user: Optional[discord.Member] = None):
        """View your or another user's inventory"""
        target = user or ctx.author

        async with self.get_db() as db:
            cursor = await db.execute("""
                SELECT 
                    i.item_id,
                    s.name,
                    i.quantity,
                    s.description
                FROM user_inventory i
                JOIN shop_items s ON i.item_id = s.id
                WHERE i.user_id = ?
                ORDER BY i.purchased_at DESC
            """, (target.id,))

            items = await cursor.fetchall()

            if not items:
                return await ctx.send(
                    f"{'Your' if target == ctx.author else target.display_name + "'s"} inventory is empty.",
                    ephemeral=target != ctx.author
                )

            # Create paginated embeds
            pages = []
            items_per_page = 5

            for i in range(0, len(items), items_per_page):
                page_items = items[i:i + items_per_page]
                embed = discord.Embed(
                    title=f"🎒 {target.display_name}'s Inventory",
                    color=0x9B59B6
                )

                for item in page_items:
                    info = f"**Quantity:** {item['quantity']:,}"
                    if item['description']:
                        info += f"\n{item['description']}"

                    embed.add_field(
                        name=f"#{item['item_id']} - {item['name']}",
                        value=info,
                        inline=False
                    )

                if len(items) > items_per_page:
                    embed.set_footer(
                        text=f"Page {i // items_per_page + 1}/{(len(items) - 1) // items_per_page + 1}"
                    )

                pages.append(embed)

            if len(pages) == 1:
                await ctx.send(embed=pages[0])
            else:
                # Implement pagination here if needed
                await ctx.send(embed=pages[0])  # For now, just send first page

    @commands.hybrid_command()
    @CovenTools.is_warlock()
    @app_commands.describe(
        name="Item name",
        description="Item description",
        price="Item price",
        role_id="Role to give (optional)",
        stock="Stock amount (-1 for unlimited)",
        max_per_user="Max per user (0 for unlimited)"
    )
    async def additem(
        self,
        ctx,
        name: str,
        description: str,
        price: int,
        role_id: Optional[int] = None,
        stock: int = -1,
        max_per_user: int = 1
    ):
        """Add an item to the shop (Warlocks only)"""
        if price < 0:
            return await ctx.send("❌ Price cannot be negative.", ephemeral=True)

        if stock < -1:
            return await ctx.send("❌ Invalid stock amount.", ephemeral=True)

        if max_per_user < 0:
            return await ctx.send("❌ Invalid max per user value.", ephemeral=True)

        try:
            async with self.get_db() as db:
                await db.execute("""
                    INSERT INTO shop_items 
                    (name, description, price, role_id, stock, max_per_user)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (name, description, price, role_id, stock, max_per_user))

                await ctx.send(
                    f"✅ Added **{name}** to the shop for {price} {self.currency_emoji}",
                    ephemeral=True
                )
        except sqlite3.IntegrityError:
            await ctx.send("❌ An item with this name already exists.", ephemeral=True)
        except Exception:
            await ctx.send("❌ An error occurred while adding the item.", ephemeral=True)
            raise

    @commands.hybrid_command()
    @CovenTools.is_warlock()
    @app_commands.describe(item_id="ID of the item to remove")
    async def removeitem(self, ctx, item_id: int):
        """Remove an item from the shop (Warlocks only)"""
        try:
            async with self.get_db() as db:
                # Get item name for the message
                cursor = await db.execute(
                    "SELECT name FROM shop_items WHERE id = ?",
                    (item_id,)
                )
                item = await cursor.fetchone()

                if not item:
                    return await ctx.send("❌ Item not found.", ephemeral=True)

                # Delete the item
                await db.execute(
                    "DELETE FROM shop_items WHERE id = ?",
                    (item_id,)
                )

                await ctx.send(
                    f"✅ **{item['name']}** has been removed from the shop.",
                    ephemeral=True
                )
        except Exception:
            await ctx.send("❌ An error occurred while removing the item.", ephemeral=True)
            raise

    @commands.hybrid_command()
    @CovenTools.is_warlock()
    @app_commands.describe(
        user="User to modify",
        amount="Amount to add (can be negative)",
        reason="Reason for modification"
    )
    async def modifybalance(
        self,
        ctx,
        user: discord.Member,
        amount: int,
        reason: str
    ):
        """Modify a user's crystal balance (Warlocks only)"""
        if user.bot:
            return await ctx.send("❌ Cannot modify bot balances.", ephemeral=True)

        if amount == 0:
            return await ctx.send("❌ Amount cannot be zero.", ephemeral=True)

        try:
            new_balance = await self._update_balance(
                user.id,
                amount,
                "admin_modification",
                f"{ctx.author.id}:{reason}"
            )

            action = "added to" if amount > 0 else "removed from"
            embed = discord.Embed(
                title="💰 Balance Modified",
                description=(
                    f"{abs(amount):,} {self.currency_emoji} {action} {user.mention}'s balance\n"
                    f"**Reason:** {reason}\n"
                    f"**New Balance:** {new_balance:,} {self.currency_emoji}"
                ),
                color=0x2ECC71 if amount > 0 else 0xE74C3C
            )
            embed.set_footer(text=f"Action by {ctx.author}", icon_url=ctx.author.display_avatar.url)

            await ctx.send(embed=embed)

        except Exception:
            await ctx.send("❌ An error occurred while modifying the balance.", ephemeral=True)
            raise

    @commands.hybrid_command()
    @CovenTools.is_warlock()
    async def listitems(self, ctx):
        """List all shop items (Warlocks only)"""
        async with self.get_db() as db:
            cursor = await db.execute("""
                SELECT 
                    id, name, price, stock, 
                    (SELECT COUNT(*) FROM user_inventory WHERE item_id = shop_items.id) as total_purchased
                FROM shop_items
                ORDER BY id
            """)

            items = await cursor.fetchall()

            if not items:
                return await ctx.send("The shop is empty.", ephemeral=True)

            embed = discord.Embed(
                title="🛍️ Shop Items",
                description="All available items in the shop",
                color=0x9B59B6
            )

            for item in items:
                info = f"**Price:** {item['price']:,} {self.currency_emoji}\n"
                info += f"**In Stock:** {item['stock'] if item['stock'] != -1 else '∞'}\n"
                info += f"**Total Purchased:** {item['total_purchased']:,}"

                embed.add_field(
                    name=f"#{item['id']} - {item['name']}",
                    value=info,
                    inline=False
                )

            await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command()
    @CovenTools.is_warlock()
    @app_commands.describe(user="User to check transactions for", limit="Number of transactions to show (max 20)")
    async def transactions(
        self,
        ctx,
        user: Optional[discord.Member] = None,
        limit: int = 10
    ):
        """View transaction history (Warlocks only)"""
        limit = max(1, min(20, limit))  # Clamp between 1 and 20

        async with self.get_db() as db:
            if user:
                cursor = await db.execute("""
                    SELECT 
                        t.amount, 
                        t.type, 
                        t.reference, 
                        t.timestamp
                    FROM transactions t
                    WHERE t.user_id = ?
                    ORDER BY t.timestamp DESC
                    LIMIT ?
                """, (user.id, limit))
                title = f"Transactions for {user.display_name}"
            else:
                cursor = await db.execute("""
                    SELECT 
                        t.user_id,
                        t.amount, 
                        t.type, 
                        t.reference, 
                        t.timestamp
                    FROM transactions t
                    ORDER BY t.timestamp DESC
                    LIMIT ?
                """, (limit,))
                title = "Recent Transactions"

            transactions = await cursor.fetchall()

            if not transactions:
                return await ctx.send("No transactions found.", ephemeral=True)

            embed = discord.Embed(
                title=title,
                description=f"Showing {len(transactions)} most recent transactions",
                color=0x9B59B6
            )

            for txn in transactions:
                # Format timestamp
                timestamp = datetime.fromisoformat(txn['timestamp'])
                time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")

                # Format amount with sign
                amount_str = f"+{txn['amount']:,}" if txn['amount'] > 0 else f"-{abs(txn['amount']):,}"

                # Get username if available
                user_ref = ""
                if 'user_id' in txn:
                    user_obj = self.bot.get_user(txn['user_id'])
                    user_ref = f" ({user_obj.display_name if user_obj else 'Unknown'})"

                # Add field
                embed.add_field(
                    name=f"{time_str} - {txn['type'].title()}",
                    value=(
                        f"**Amount:** {amount_str} {self.currency_emoji}\n"
                        f"**Reference:** {txn['reference'] or 'N/A'}{user_ref}"
                    ),
                    inline=False
                )

            await ctx.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Economy(bot))
