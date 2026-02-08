"""
TheCohen Casino Bot - Complete Discord Casino Bot
Fixed blackjack, MT game with proper display, and admin commands

SETUP INSTRUCTIONS:
1. Add your Discord user ID to ADMIN_IDS list (line ~26)
2. Add admin role IDs to ADMIN_ROLE_IDS list (line ~30) - OPTIONAL
   - Users with these roles will have admin permissions
   - To get role ID: Server Settings > Roles > Right-click role > Copy ID
   - Example: ADMIN_ROLE_IDS = [1234567890, 9876543210]
3. Add your casino channel IDs to CASINO_CHANNEL_IDS list (line ~35)
   - To get channel ID: Right-click channel > Copy ID (enable Developer Mode in Discord settings)
   - Example: CASINO_CHANNEL_IDS = [1234567890, 9876543210]
   - Leave empty [] to check for 'casino' or 'קסינו' in channel name
4. Adjust cooldowns if needed (lines ~38-41)
5. Add your bot token at the bottom of the file (line ~1587)
"""

import discord
from discord.ext import commands
from discord.ui import Button, View
import random
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional

# ============================================================================
# BOT SETUP
# ============================================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='$', intents=intents, help_command=None)

# Admin user IDs (replace with your Discord user IDs)
ADMIN_IDS = [1123938672866234378]  # Add your admin IDs here

# Admin role IDs - Users with these roles can use admin commands
# To get role ID: Right-click role > Copy ID (enable Developer Mode)
# Example: ADMIN_ROLE_IDS = [1234567890123456, 9876543210987654]
ADMIN_ROLE_IDS = [1444695109190029378,1468004851752632537]  # Add role IDs here

# Casino channel IDs - Add your casino channel IDs here
# Example: CASINO_CHANNEL_IDS = [123456789012345678, 987654321098765432]
CASINO_CHANNEL_IDS = [1469451103903940608,1469451273978773679,1469451273978773679,1469451332548034695,1469451387770376444]  # If empty, will check for 'casino' or 'קסינו' in channel name

# Cooldowns (in minutes)
WORK_COOLDOWN = 3
CRIME_COOLDOWN = 3
ROB_COOLDOWN = 7
HELP_COOLDOWN = 1

@bot.event
async def on_ready():
    print(f'{bot.user.name} is online!')
    await bot.change_presence(activity=discord.Game(name="🎰 $help"))


# ============================================================================
# CASINO CHANNEL CHECK
# ============================================================================

def is_admin(ctx):
    """Check if user is admin by user ID or role ID"""
    # Check if user ID is in admin list
    if ctx.author.id in ADMIN_IDS:
        return True
    
    # Check if user has any of the admin roles
    if ADMIN_ROLE_IDS and hasattr(ctx.author, 'roles'):
        user_role_ids = [role.id for role in ctx.author.roles]
        if any(role_id in ADMIN_ROLE_IDS for role_id in user_role_ids):
            return True
    
    return False

def is_casino_channel(ctx):
    """Check if command is used in a casino channel"""
    # If specific channel IDs are set, use those
    if CASINO_CHANNEL_IDS:
        return ctx.channel.id in CASINO_CHANNEL_IDS
    # Otherwise, check channel name
    channel_name = ctx.channel.name.lower()
    return 'casino' in channel_name or 'קסינו' in channel_name

async def casino_channel_only(ctx):
    """Send error message if not in casino channel"""
    if not is_casino_channel(ctx):
        embed = discord.Embed(color=0xED4245)
        embed.description = "🎰 Please use casino commands only in casino channels!"
        await ctx.send(embed=embed, delete_after=5)
        return False
    return True


# ============================================================================
# ECONOMY MANAGER
# ============================================================================

class EconomyManager:
    def __init__(self, filename='economy.json'):
        self.filename = filename
        self.data = self.load_data()
    
    def load_data(self):
        try:
            with open(self.filename, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
    
    def save_data(self):
        with open(self.filename, 'w') as f:
            json.dump(self.data, f, indent=4)
    
    def get_user(self, user_id):
        user_id = str(user_id)
        if user_id not in self.data:
            self.data[user_id] = {
                'cash': 0,
                'bank': 0,
                'last_work': None,
                'last_crime': None,
                'last_rob': None,
                'last_collect': None,
                'last_streak': None,
                'streak_count': 0
            }
            self.save_data()
        return self.data[user_id]
    
    def get_cash(self, user_id):
        return self.get_user(user_id)['cash']
    
    def get_bank(self, user_id):
        return self.get_user(user_id)['bank']
    
    def get_total(self, user_id):
        user = self.get_user(user_id)
        return user['cash'] + user['bank']
    
    def add_cash(self, user_id, amount):
        user_id = str(user_id)
        self.get_user(user_id)
        self.data[user_id]['cash'] += amount
        self.save_data()
        return self.data[user_id]['cash']
    
    def remove_cash(self, user_id, amount):
        user_id = str(user_id)
        cash = self.get_cash(user_id)
        if cash < amount:
            return None
        self.data[user_id]['cash'] -= amount
        self.save_data()
        return self.data[user_id]['cash']
    
    def add_bank(self, user_id, amount):
        user_id = str(user_id)
        self.get_user(user_id)
        self.data[user_id]['bank'] += amount
        self.save_data()
        return self.data[user_id]['bank']
    
    def remove_bank(self, user_id, amount):
        user_id = str(user_id)
        bank = self.get_bank(user_id)
        if bank < amount:
            return None
        self.data[user_id]['bank'] -= amount
        self.save_data()
        return self.data[user_id]['bank']

economy = EconomyManager()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def parse_amount(amount_str, user_id, use_cash=True):
    """Parse amount string (number or 'all')"""
    if amount_str.lower() == 'all':
        if use_cash:
            return economy.get_cash(user_id)
        else:
            return economy.get_bank(user_id)
    try:
        return int(amount_str)
    except:
        return None


# ============================================================================
# ADMIN COMMANDS
# ============================================================================

@bot.command(name='addmoney', aliases=['givemoney'])
async def addmoney(ctx, member: discord.Member, amount: int):
    """Admin only - Add money to a user"""
    if not is_admin(ctx):
        await ctx.send("❌ You don't have permission to use this command!")
        return
    
    if amount <= 0:
        await ctx.send("❌ Amount must be positive!")
        return
    
    economy.add_cash(member.id, amount)
    
    embed = discord.Embed(color=0x57F287)
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
    embed.description = f"✅ Added **${amount:,}** 💵 to {member.mention}'s cash!"
    
    await ctx.send(embed=embed)


@bot.command(name='removemoney', aliases=['takemoney'])
async def removemoney(ctx, member: discord.Member, amount: int):
    """Admin only - Remove money from a user"""
    if not is_admin(ctx):
        await ctx.send("❌ You don't have permission to use this command!")
        return
    
    if amount <= 0:
        await ctx.send("❌ Amount must be positive!")
        return
    
    economy.remove_cash(member.id, amount)
    
    embed = discord.Embed(color=0xED4245)
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
    embed.description = f"✅ Removed **${amount:,}** 💵 from {member.mention}'s cash!"
    
    await ctx.send(embed=embed)


@bot.command(name='setmoney')
async def setmoney(ctx, member: discord.Member, amount: int):
    """Admin only - Set a user's money"""
    if not is_admin(ctx):
        await ctx.send("❌ You don't have permission to use this command!")
        return
    
    if amount < 0:
        await ctx.send("❌ Amount cannot be negative!")
        return
    
    user_id = str(member.id)
    economy.get_user(member.id)
    economy.data[user_id]['cash'] = amount
    economy.save_data()
    
    embed = discord.Embed(color=0x5865F2)
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
    embed.description = f"✅ Set {member.mention}'s cash to **${amount:,}** 💵!"
    
    await ctx.send(embed=embed)


# ============================================================================
# BALANCE COMMANDS
# ============================================================================

@bot.command(name='bal', aliases=['balance'])
async def balance(ctx, member: Optional[discord.Member] = None):
    """Check balance - $bal [@user]"""
    target = member or ctx.author
    
    cash = economy.get_cash(target.id)
    bank = economy.get_bank(target.id)
    total = cash + bank
    
    embed = discord.Embed(color=0x5865F2)
    embed.set_author(name=target.display_name, icon_url=target.display_avatar.url)
    embed.add_field(name="💵 Cash", value=f"${cash:,}", inline=True)
    embed.add_field(name="🏦 Bank", value=f"${bank:,}", inline=True)
    embed.add_field(name="💰 Total", value=f"${total:,}", inline=True)
    
    await ctx.send(embed=embed)


@bot.command(name='top', aliases=['lb', 'leaderboard'])
async def leaderboard(ctx, category: str = 'total'):
    """Leaderboard - $top [cash/bank/total]"""
    category = category.lower()
    if category not in ['cash', 'bank', 'total']:
        category = 'total'
    
    users = []
    for user_id, data in economy.data.items():
        if category == 'cash':
            value = data['cash']
        elif category == 'bank':
            value = data['bank']
        else:
            value = data['cash'] + data['bank']
        users.append((user_id, value))
    
    users.sort(key=lambda x: x[1], reverse=True)
    top_10 = users[:10]
    
    embed = discord.Embed(
        title=f"🏆 Top Players - {category.capitalize()}",
        color=0xFFD700
    )
    
    description = ""
    for i, (user_id, value) in enumerate(top_10, 1):
        try:
            user = await bot.fetch_user(int(user_id))
            description += f"**{i}.** {user.mention} - ${value:,}\n"
        except:
            description += f"**{i}.** Unknown User - ${value:,}\n"
    
    embed.description = description if description else "No data yet!"
    await ctx.send(embed=embed)


# ============================================================================
# MONEY TRANSFER COMMANDS
# ============================================================================

@bot.command(name='dep', aliases=['deposit'])
async def deposit(ctx, amount: str):
    """Deposit money to bank - $dep <amount/all>"""
    amt = parse_amount(amount, ctx.author.id, use_cash=True)
    
    if amt is None or amt <= 0:
        await ctx.send("❌ Invalid amount!")
        return
    
    cash = economy.get_cash(ctx.author.id)
    if cash < amt:
        await ctx.send(f"❌ You don't have enough cash! You have ${cash:,}")
        return
    
    economy.remove_cash(ctx.author.id, amt)
    new_bank = economy.add_bank(ctx.author.id, amt)
    
    embed = discord.Embed(color=0x57F287)
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
    embed.description = f"You deposited **${amt:,}** into your bank!\nNew bank balance: **${new_bank:,}** 🏦"
    
    await ctx.send(embed=embed)


@bot.command(name='with', aliases=['withdraw'])
async def withdraw(ctx, amount: str):
    """Withdraw money from bank - $with <amount/all>"""
    amt = parse_amount(amount, ctx.author.id, use_cash=False)
    
    if amt is None or amt <= 0:
        await ctx.send("❌ Invalid amount!")
        return
    
    bank = economy.get_bank(ctx.author.id)
    if bank < amt:
        await ctx.send(f"❌ You don't have enough money in the bank! You have ${bank:,}")
        return
    
    economy.remove_bank(ctx.author.id, amt)
    new_cash = economy.add_cash(ctx.author.id, amt)
    
    embed = discord.Embed(color=0x57F287)
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
    embed.description = f"You withdrew **${amt:,}** from your bank!\nNew cash balance: **${new_cash:,}** 💵"
    
    await ctx.send(embed=embed)


@bot.command(name='pay', aliases=['give'])
async def pay(ctx, member: discord.Member, amount: str):
    """Give money to someone - $pay <@user> <amount/all>"""
    if member.id == ctx.author.id:
        await ctx.send("❌ You can't pay yourself!")
        return
    
    amt = parse_amount(amount, ctx.author.id, use_cash=True)
    
    if amt is None or amt <= 0:
        await ctx.send("❌ Invalid amount!")
        return
    
    cash = economy.get_cash(ctx.author.id)
    if cash < amt:
        await ctx.send(f"❌ You don't have enough cash! You have ${cash:,}")
        return
    
    economy.remove_cash(ctx.author.id, amt)
    economy.add_cash(member.id, amt)
    
    embed = discord.Embed(color=0x57F287)
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
    embed.description = f"You gave **${amt:,}** 💵 to {member.mention}!"
    
    await ctx.send(embed=embed)


# ============================================================================
# EARNING COMMANDS
# ============================================================================

@bot.command(name='work')
async def work(ctx):
    """Work for money - $work (3 min cooldown)"""
    if not await casino_channel_only(ctx):
        return
    
    user_id = str(ctx.author.id)
    user = economy.get_user(ctx.author.id)
    
    last_work = user.get('last_work')
    now = datetime.now()
    
    if last_work:
        last_work_dt = datetime.fromisoformat(last_work)
        if now - last_work_dt < timedelta(minutes=WORK_COOLDOWN):
            time_left = timedelta(minutes=WORK_COOLDOWN) - (now - last_work_dt)
            seconds = time_left.seconds
            await ctx.send(f"⏱️ You can work again in **{seconds // 60}m {seconds % 60}s**")
            return
    
    earnings = random.randint(4000, 12000)
    economy.add_cash(ctx.author.id, earnings)
    economy.data[user_id]['last_work'] = now.isoformat()
    economy.save_data()
    
    embed = discord.Embed(color=0x57F287)
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
    embed.description = f"You worked hard and got **{earnings:,}** 💵!"
    
    await ctx.send(embed=embed)


@bot.command(name='crime')
async def crime(ctx):
    """Commit a crime - $crime (3 min cooldown)"""
    if not await casino_channel_only(ctx):
        return
    
    user_id = str(ctx.author.id)
    user = economy.get_user(ctx.author.id)
    
    last_crime = user.get('last_crime')
    now = datetime.now()
    
    if last_crime:
        last_crime_dt = datetime.fromisoformat(last_crime)
        if now - last_crime_dt < timedelta(minutes=CRIME_COOLDOWN):
            time_left = timedelta(minutes=CRIME_COOLDOWN) - (now - last_crime_dt)
            seconds = time_left.seconds
            await ctx.send(f"⏱️ You can commit a crime again in **{seconds // 60}m {seconds % 60}s**")
            return
    
    success = random.random() > 0.35  # 65% success rate
    
    if success:
        earnings = random.randint(6000, 15000)
        economy.add_cash(ctx.author.id, earnings)
        
        embed = discord.Embed(color=0x57F287)
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.description = f"You successfully committed a crime and got **{earnings:,}** 💵!"
    else:
        fine = random.randint(2000, 8000)
        economy.remove_cash(ctx.author.id, min(fine, economy.get_cash(ctx.author.id)))
        
        embed = discord.Embed(color=0xED4245)
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.description = f"You got caught! You paid a fine of **{fine:,}** 💵! 🚨"
    
    economy.data[user_id]['last_crime'] = now.isoformat()
    economy.save_data()
    
    await ctx.send(embed=embed)


@bot.command(name='rob')
async def rob(ctx, member: discord.Member):
    """Rob someone - $rob <@user> (7 min cooldown)"""
    if not await casino_channel_only(ctx):
        return
    
    if member.id == ctx.author.id:
        await ctx.send("❌ You can't rob yourself!")
        return
    
    if member.bot:
        await ctx.send("❌ You can't rob a bot!")
        return
    
    user_id = str(ctx.author.id)
    user = economy.get_user(ctx.author.id)
    
    last_rob = user.get('last_rob')
    now = datetime.now()
    
    if last_rob:
        last_rob_dt = datetime.fromisoformat(last_rob)
        if now - last_rob_dt < timedelta(minutes=ROB_COOLDOWN):
            time_left = timedelta(minutes=ROB_COOLDOWN) - (now - last_rob_dt)
            minutes = time_left.seconds // 60
            seconds = time_left.seconds % 60
            await ctx.send(f"⏱️ You can rob again in **{minutes}m {seconds}s**")
            return
    
    target_cash = economy.get_cash(member.id)
    
    if target_cash < 1000:
        await ctx.send(f"❌ {member.display_name} doesn't have enough money to rob!")
        return
    
    success = random.random() > 0.40  # 60% success rate
    
    if success:
        stolen = random.randint(int(target_cash * 0.1), int(target_cash * 0.4))
        economy.remove_cash(member.id, stolen)
        economy.add_cash(ctx.author.id, stolen)
        
        embed = discord.Embed(color=0x57F287)
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.description = f"You successfully robbed **${stolen:,}** 💵 from {member.mention}!"
    else:
        fine = random.randint(1000, 5000)
        economy.remove_cash(ctx.author.id, min(fine, economy.get_cash(ctx.author.id)))
        
        embed = discord.Embed(color=0xED4245)
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.description = f"You failed to rob {member.mention} and paid a fine of **${fine:,}** 💵!"
    
    economy.data[user_id]['last_rob'] = now.isoformat()
    economy.save_data()
    
    await ctx.send(embed=embed)


@bot.command(name='collect')
async def collect(ctx):
    """Collect reward - $collect (12 hour cooldown)"""
    user_id = str(ctx.author.id)
    user = economy.get_user(ctx.author.id)
    
    last_collect = user.get('last_collect')
    now = datetime.now()
    
    if last_collect:
        last_collect_dt = datetime.fromisoformat(last_collect)
        if now - last_collect_dt < timedelta(hours=12):
            time_left = timedelta(hours=12) - (now - last_collect_dt)
            hours = time_left.seconds // 3600
            minutes = (time_left.seconds % 3600) // 60
            await ctx.send(f"⏱️ You can collect again in **{hours}h {minutes}m**")
            return
    
    reward = random.randint(10000, 25000)
    economy.add_cash(ctx.author.id, reward)
    economy.data[user_id]['last_collect'] = now.isoformat()
    economy.save_data()
    
    embed = discord.Embed(color=0x57F287)
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
    embed.description = f"You collected **{reward:,}** 💵!"
    
    await ctx.send(embed=embed)


@bot.command(name='streak')
async def streak(ctx):
    """Daily streak reward - $streak (24 hour cooldown)"""
    user_id = str(ctx.author.id)
    user = economy.get_user(ctx.author.id)
    
    last_streak = user.get('last_streak')
    now = datetime.now()
    
    if last_streak:
        last_streak_dt = datetime.fromisoformat(last_streak)
        time_diff = now - last_streak_dt
        
        if time_diff < timedelta(hours=24):
            time_left = timedelta(hours=24) - time_diff
            hours = time_left.seconds // 3600
            minutes = (time_left.seconds % 3600) // 60
            
            embed = discord.Embed(color=0xED4245)
            embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
            embed.description = f"🚫 You already claimed your daily streak reward!\nCome back in **{hours}h {minutes}m**"
            await ctx.send(embed=embed)
            return
        
        # Check if streak continues (within 48 hours)
        if time_diff < timedelta(hours=48):
            streak_count = user.get('streak_count', 0) + 1
        else:
            streak_count = 1
    else:
        streak_count = 1
    
    reward = 5000 + (streak_count * 1000)  # Base 5000 + 1000 per day
    economy.add_cash(ctx.author.id, reward)
    economy.data[user_id]['last_streak'] = now.isoformat()
    economy.data[user_id]['streak_count'] = streak_count
    economy.save_data()
    
    embed = discord.Embed(color=0x57F287)
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
    embed.description = f"🔥 **{streak_count} Day Streak!**\nYou received **{reward:,}** 💵!"
    
    await ctx.send(embed=embed)


# ============================================================================
# MT GAME (3x5 MINES) - MATCHING SCREENSHOT
# ============================================================================

class MTView(View):
    def __init__(self, user, bet):
        super().__init__(timeout=120)
        self.user = user
        self.bet = bet
        self.rows = 3
        self.cols = 5
        self.revealed = [[False] * self.cols for _ in range(self.rows)]
        self.bombs = set()
        self.profit = 0
        self.multiplier = 1.0
        self.game_over = False
        
        # Place 5 bombs randomly
        num_bombs = 5
        while len(self.bombs) < num_bombs:
            self.bombs.add((random.randint(0, self.rows-1), random.randint(0, self.cols-1)))
        
        # Create buttons (3 rows x 5 columns)
        for i in range(self.rows):
            for j in range(self.cols):
                button = Button(style=discord.ButtonStyle.secondary, label="?", row=i, custom_id=f"tile_{i}_{j}")
                button.callback = self.make_callback(i, j)
                self.add_item(button)
        
        # Add cashout button in row 4
        cashout_btn = Button(style=discord.ButtonStyle.success, label="Cashout", row=4)
        cashout_btn.callback = self.cashout
        self.add_item(cashout_btn)
    
    def make_callback(self, i, j):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                await interaction.response.send_message("This isn't your game!", ephemeral=True)
                return
            
            if self.game_over:
                return
            
            if self.revealed[i][j]:
                await interaction.response.defer()
                return
            
            self.revealed[i][j] = True
            
            if (i, j) in self.bombs:
                # Hit a bomb
                self.game_over = True
                for item in self.children:
                    item.disabled = True
                
                # Reveal all bombs
                for bi, bj in self.bombs:
                    idx = bi * self.cols + bj
                    self.children[idx].label = "💣"
                    self.children[idx].style = discord.ButtonStyle.danger
                
                # Show revealed safe tiles
                for ri in range(self.rows):
                    for rj in range(self.cols):
                        if self.revealed[ri][rj] and (ri, rj) not in self.bombs:
                            idx = ri * self.cols + rj
                            self.children[idx].label = "$"
                            self.children[idx].style = discord.ButtonStyle.success
                
                embed = discord.Embed(color=0xED4245)
                embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
                embed.description = f"💥 You hit a bomb and lost **${self.bet:,}** 💵!"
                embed.add_field(name="Profit", value=f"-{self.bet:,} 💵", inline=True)
                
                economy.remove_cash(interaction.user.id, self.bet)
                
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                # Safe tile
                self.multiplier += 0.25
                self.profit = int(self.bet * self.multiplier) - self.bet
                
                idx = i * self.cols + j
                self.children[idx].label = "$"
                self.children[idx].style = discord.ButtonStyle.success
                
                embed = discord.Embed(color=0x5865F2)
                embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
                embed.description = f"Click tiles to reveal! Avoid the bombs 💣"
                embed.add_field(name="Profit", value=f"{self.profit:,} 💵", inline=True)
                
                await interaction.response.edit_message(embed=embed, view=self)
        
        return callback
    
    async def cashout(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        if self.game_over:
            return
        
        self.game_over = True
        for item in self.children:
            item.disabled = True
        
        winnings = int(self.bet * self.multiplier)
        profit = winnings - self.bet
        economy.add_cash(interaction.user.id, profit)
        
        embed = discord.Embed(color=0x57F287)
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.description = f"💰 You cashed out successfully!"
        embed.add_field(name="Profit", value=f"{profit:,} 💵", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=self)


@bot.command(name='mt')
async def mt_game(ctx, amount: str):
    """Play MT game (3x5 mines) - $mt <amount/all>"""
    if not await casino_channel_only(ctx):
        return
    
    bet = parse_amount(amount, ctx.author.id, use_cash=True)
    
    if bet is None or bet < 100:
        await ctx.send("❌ Minimum bet is $100!")
        return
    
    cash = economy.get_cash(ctx.author.id)
    if cash < bet:
        await ctx.send(f"❌ You don't have enough cash! You currently have ${cash:,} 💵")
        return
    
    view = MTView(ctx.author, bet)
    
    embed = discord.Embed(color=0x5865F2)
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
    embed.description = f"Click tiles to reveal! Avoid the bombs 💣"
    embed.add_field(name="Profit", value="0 💵", inline=True)
    
    await ctx.send(embed=embed, view=view)


# ============================================================================
# SLOT MACHINE WITH BUTTONS
# ============================================================================

class SlotView(View):
    def __init__(self, user, bet):
        super().__init__(timeout=60)
        self.user = user
        self.bet = bet
        self.spinning = False
        
        spin_btn = Button(label="🎰 Spin", style=discord.ButtonStyle.primary)
        spin_btn.callback = self.spin
        self.add_item(spin_btn)
    
    async def spin(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        if self.spinning:
            await interaction.response.defer()
            return
        
        self.spinning = True
        
        # Disable button
        for item in self.children:
            item.disabled = True
        
        symbols = ['🍒', '🍋', '🍊', '🍇', '💎', '7️⃣', '🔔']
        
        # Animate spinning
        for _ in range(3):
            temp_result = [random.choice(symbols) for _ in range(3)]
            embed = discord.Embed(color=0x5865F2)
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            embed.description = f"🎰 | {' '.join(temp_result)} |\n\n**Spinning...**"
            await interaction.response.edit_message(embed=embed, view=self) if _ == 0 else await interaction.edit_original_response(embed=embed, view=self)
            await asyncio.sleep(0.5)
        
        # Final result
        result = [random.choice(symbols) for _ in range(3)]
        
        # Calculate winnings
        if result[0] == result[1] == result[2]:
            if result[0] == '7️⃣':
                multiplier = 20
            elif result[0] == '💎':
                multiplier = 15
            elif result[0] == '🔔':
                multiplier = 10
            else:
                multiplier = 5
            profit = self.bet * multiplier - self.bet
            economy.add_cash(self.user.id, profit)
            color = 0x57F287
            outcome = f"🎉 **JACKPOT!** You won **{profit:,}** 💵 (x{multiplier})"
        elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
            multiplier = 2
            profit = self.bet * multiplier - self.bet
            economy.add_cash(self.user.id, profit)
            color = 0x57F287
            outcome = f"✨ You won **{profit:,}** 💵 (x{multiplier})"
        else:
            economy.remove_cash(self.user.id, self.bet)
            color = 0xED4245
            outcome = f"You lost **{self.bet:,}** 💵"
        
        embed = discord.Embed(color=color)
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.description = f"🎰 | {' '.join(result)} |\n\n{outcome}"
        
        await interaction.edit_original_response(embed=embed, view=self)


@bot.command(name='sm', aliases=['slots'])
async def slotmachine(ctx, amount: str):
    """Play slot machine - $sm <amount/all>"""
    if not await casino_channel_only(ctx):
        return
    
    bet = parse_amount(amount, ctx.author.id, use_cash=True)
    
    if bet is None or bet < 10:
        await ctx.send("❌ Minimum bet is $10!")
        return
    
    cash = economy.get_cash(ctx.author.id)
    if cash < bet:
        await ctx.send(f"❌ You don't have enough cash! You currently have ${cash:,} 💵")
        return
    
    view = SlotView(ctx.author, bet)
    
    embed = discord.Embed(color=0x5865F2)
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
    embed.description = f"🎰 Slot Machine\n**Bet: ${bet:,}**\n\nClick spin to play!"
    
    await ctx.send(embed=embed, view=view)


# ============================================================================
# CHICKEN FIGHT WITH BUTTONS
# ============================================================================

class ChickenView(View):
    def __init__(self, user, bet):
        super().__init__(timeout=60)
        self.user = user
        self.bet = bet
        self.current_bet = bet
        self.rounds = 0
        self.win_chance = 0.45
        
        fight_btn = Button(label="🐔 Fight", style=discord.ButtonStyle.danger)
        fight_btn.callback = self.fight
        self.add_item(fight_btn)
        
        cashout_btn = Button(label="💰 Cashout", style=discord.ButtonStyle.success)
        cashout_btn.callback = self.cashout
        self.add_item(cashout_btn)
    
    async def fight(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        self.rounds += 1
        wins = random.random() < self.win_chance
        
        if wins:
            self.current_bet = int(self.current_bet * 2)
            self.win_chance += 0.05  # Increase chance each win
            
            embed = discord.Embed(color=0x57F287)
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            embed.description = f"🐔 **Your chicken won!**\n\nRound: {self.rounds}\nCurrent Winnings: **${self.current_bet:,}** 💵\nWin Chance: {int(self.win_chance * 100)}%"
            
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            # Lost - disable buttons
            for item in self.children:
                item.disabled = True
            
            economy.remove_cash(self.user.id, self.bet)
            
            embed = discord.Embed(color=0xED4245)
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            embed.description = f"🦅 **Your chicken lost the fight!**\n\nYou lost **${self.bet:,}** 💵 after {self.rounds} rounds"
            
            await interaction.response.edit_message(embed=embed, view=self)
    
    async def cashout(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        for item in self.children:
            item.disabled = True
        
        profit = self.current_bet - self.bet
        economy.add_cash(self.user.id, profit)
        
        embed = discord.Embed(color=0x57F287)
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.description = f"💰 **Cashed out!**\n\nProfit: **${profit:,}** 💵\nRounds survived: {self.rounds}"
        
        await interaction.response.edit_message(embed=embed, view=self)


@bot.command(name='cf', aliases=['chicken'])
async def chickenfight(ctx, amount: str):
    """Chicken fight - $cf <amount>"""
    if not await casino_channel_only(ctx):
        return
    
    bet = parse_amount(amount, ctx.author.id, use_cash=True)
    
    if bet is None or bet < 10:
        await ctx.send("❌ Minimum bet is $10!")
        return
    
    cash = economy.get_cash(ctx.author.id)
    if cash < bet:
        await ctx.send(f"❌ You don't have enough cash! You currently have ${cash:,} 💵")
        return
    
    view = ChickenView(ctx.author, bet)
    
    embed = discord.Embed(color=0x5865F2)
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
    embed.description = f"🐔 **Chicken Fight**\n\nBet: **${bet:,}**\nWin Chance: 45%\n\nFight to double your money or cashout anytime!"
    
    await ctx.send(embed=embed, view=view)


# ============================================================================
# COINFLIP / HEADS OR TAILS WITH BUTTONS
# ============================================================================

class CoinflipView(View):
    def __init__(self, user, bet):
        super().__init__(timeout=30)
        self.user = user
        self.bet = bet
        
        heads_btn = Button(label="🪙 Heads", style=discord.ButtonStyle.primary)
        heads_btn.callback = self.choose_heads
        self.add_item(heads_btn)
        
        tails_btn = Button(label="🪙 Tails", style=discord.ButtonStyle.primary)
        tails_btn.callback = self.choose_tails
        self.add_item(tails_btn)
    
    async def flip_coin(self, interaction: discord.Interaction, choice: str):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        for item in self.children:
            item.disabled = True
        
        result = random.choice(['heads', 'tails'])
        
        # Animation
        embed = discord.Embed(color=0x5865F2)
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.description = "🪙 **Flipping...**"
        await interaction.response.edit_message(embed=embed, view=self)
        await asyncio.sleep(1)
        
        if result == choice:
            profit = self.bet
            economy.add_cash(self.user.id, profit)
            
            embed = discord.Embed(color=0x57F287)
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            embed.description = f"🪙 The coin landed on **{result.upper()}**!\n\n✅ You won **${profit:,}** 💵!"
        else:
            economy.remove_cash(self.user.id, self.bet)
            
            embed = discord.Embed(color=0xED4245)
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            embed.description = f"🪙 The coin landed on **{result.upper()}**!\n\n❌ You lost **${self.bet:,}** 💵!"
        
        embed.set_footer(text=f"You chose: {choice.upper()}")
        await interaction.edit_original_response(embed=embed, view=self)
    
    async def choose_heads(self, interaction: discord.Interaction):
        await self.flip_coin(interaction, 'heads')
    
    async def choose_tails(self, interaction: discord.Interaction):
        await self.flip_coin(interaction, 'tails')


@bot.command(name='ht', aliases=['coinflip'])
async def headstails(ctx, amount: str):
    """Heads or tails - $ht <amount>"""
    if not await casino_channel_only(ctx):
        return
    
    bet = parse_amount(amount, ctx.author.id, use_cash=True)
    
    if bet is None or bet < 10:
        await ctx.send("❌ Minimum bet is $10!")
        return
    
    cash = economy.get_cash(ctx.author.id)
    if cash < bet:
        await ctx.send(f"❌ You don't have enough cash! You currently have ${cash:,} 💵")
        return
    
    view = CoinflipView(ctx.author, bet)
    
    embed = discord.Embed(color=0x5865F2)
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
    embed.description = f"🪙 **Coinflip**\n\nBet: **${bet:,}**\n\nChoose heads or tails!"
    
    await ctx.send(embed=embed, view=view)


# ============================================================================
# ROCK PAPER SCISSORS WITH BUTTONS
# ============================================================================

class RPSView(View):
    def __init__(self, user, bet):
        super().__init__(timeout=30)
        self.user = user
        self.bet = bet
        
        rock_btn = Button(label="🪨 Rock", style=discord.ButtonStyle.secondary)
        rock_btn.callback = self.choose_rock
        self.add_item(rock_btn)
        
        paper_btn = Button(label="📄 Paper", style=discord.ButtonStyle.secondary)
        paper_btn.callback = self.choose_paper
        self.add_item(paper_btn)
        
        scissors_btn = Button(label="✂️ Scissors", style=discord.ButtonStyle.secondary)
        scissors_btn.callback = self.choose_scissors
        self.add_item(scissors_btn)
    
    async def play(self, interaction: discord.Interaction, choice: str):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        for item in self.children:
            item.disabled = True
        
        choices_emoji = {'rock': '🪨', 'paper': '📄', 'scissors': '✂️'}
        bot_choice = random.choice(['rock', 'paper', 'scissors'])
        
        if choice == bot_choice:
            embed = discord.Embed(color=0xFEE75C)
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            embed.description = f"You chose {choices_emoji[choice]} **{choice.upper()}**\nI chose {choices_emoji[bot_choice]} **{bot_choice.upper()}**\n\n**TIE!** Your bet is returned."
        elif (choice == 'rock' and bot_choice == 'scissors') or \
             (choice == 'paper' and bot_choice == 'rock') or \
             (choice == 'scissors' and bot_choice == 'paper'):
            profit = self.bet
            economy.add_cash(self.user.id, profit)
            
            embed = discord.Embed(color=0x57F287)
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            embed.description = f"You chose {choices_emoji[choice]} **{choice.upper()}**\nI chose {choices_emoji[bot_choice]} **{bot_choice.upper()}**\n\n✅ You won **${profit:,}** 💵!"
        else:
            economy.remove_cash(self.user.id, self.bet)
            
            embed = discord.Embed(color=0xED4245)
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            embed.description = f"You chose {choices_emoji[choice]} **{choice.upper()}**\nI chose {choices_emoji[bot_choice]} **{bot_choice.upper()}**\n\n❌ You lost **${self.bet:,}** 💵!"
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def choose_rock(self, interaction: discord.Interaction):
        await self.play(interaction, 'rock')
    
    async def choose_paper(self, interaction: discord.Interaction):
        await self.play(interaction, 'paper')
    
    async def choose_scissors(self, interaction: discord.Interaction):
        await self.play(interaction, 'scissors')


@bot.command(name='rps')
async def rockpaperscissors(ctx, amount: str):
    """Rock Paper Scissors - $rps <amount>"""
    if not await casino_channel_only(ctx):
        return
    
    bet = parse_amount(amount, ctx.author.id, use_cash=True)
    
    if bet is None or bet < 10:
        await ctx.send("❌ Minimum bet is $10!")
        return
    
    cash = economy.get_cash(ctx.author.id)
    if cash < bet:
        await ctx.send(f"❌ You don't have enough cash! You currently have ${cash:,} 💵")
        return
    
    view = RPSView(ctx.author, bet)
    
    embed = discord.Embed(color=0x5865F2)
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
    embed.description = f"🪨📄✂️ **Rock Paper Scissors**\n\nBet: **${bet:,}**\n\nMake your choice!"
    
    await ctx.send(embed=embed, view=view)


# ============================================================================
# HIGH LOW WITH BUTTONS
# ============================================================================

class HighLowView(View):
    def __init__(self, user, bet, first_card):
        super().__init__(timeout=30)
        self.user = user
        self.bet = bet
        self.first_card = first_card
        
        high_btn = Button(label="⬆️ Higher", style=discord.ButtonStyle.success)
        high_btn.callback = self.choose_high
        self.add_item(high_btn)
        
        low_btn = Button(label="⬇️ Lower", style=discord.ButtonStyle.danger)
        low_btn.callback = self.choose_low
        self.add_item(low_btn)
    
    async def play(self, interaction: discord.Interaction, choice: str):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        for item in self.children:
            item.disabled = True
        
        second_card = random.randint(2, 14)
        
        if (choice == 'high' and second_card > self.first_card) or (choice == 'low' and second_card < self.first_card):
            profit = self.bet
            economy.add_cash(self.user.id, profit)
            
            embed = discord.Embed(color=0x57F287)
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            embed.description = f"First card: **{self.first_card}**\nNext card: **{second_card}**\n\n✅ Correct! You won **${profit:,}** 💵!"
        elif second_card == self.first_card:
            embed = discord.Embed(color=0xFEE75C)
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            embed.description = f"First card: **{self.first_card}**\nNext card: **{second_card}**\n\n**Same card!** Your bet is returned."
        else:
            economy.remove_cash(self.user.id, self.bet)
            
            embed = discord.Embed(color=0xED4245)
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            embed.description = f"First card: **{self.first_card}**\nNext card: **{second_card}**\n\n❌ Wrong! You lost **${self.bet:,}** 💵!"
        
        embed.set_footer(text=f"You chose: {choice.upper()}")
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def choose_high(self, interaction: discord.Interaction):
        await self.play(interaction, 'high')
    
    async def choose_low(self, interaction: discord.Interaction):
        await self.play(interaction, 'low')


@bot.command(name='hl', aliases=['highlow'])
async def highlow(ctx, amount: str):
    """High or low game - $hl <amount>"""
    if not await casino_channel_only(ctx):
        return
    
    bet = parse_amount(amount, ctx.author.id, use_cash=True)
    
    if bet is None or bet < 10:
        await ctx.send("❌ Minimum bet is $10!")
        return
    
    cash = economy.get_cash(ctx.author.id)
    if cash < bet:
        await ctx.send(f"❌ You don't have enough cash! You currently have ${cash:,} 💵")
        return
    
    first_card = random.randint(2, 14)
    view = HighLowView(ctx.author, bet, first_card)
    
    embed = discord.Embed(color=0x5865F2)
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
    embed.description = f"🎴 **High or Low**\n\nYour card: **{first_card}**\n\nWill the next card be higher or lower?"
    
    await ctx.send(embed=embed, view=view)


# ============================================================================
# BLACKJACK - FIXED VERSION
# ============================================================================

class BlackjackView(View):
    def __init__(self, ctx, bet):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.bet = bet
        self.game_over = False
        
        suits = ['♠️', '♥️', '♦️', '♣️']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        self.deck = [f"{rank}{suit}" for suit in suits for rank in ranks] * 6
        random.shuffle(self.deck)
        
        self.player_hand = [self.deck.pop(), self.deck.pop()]
        self.dealer_hand = [self.deck.pop(), self.deck.pop()]
    
    def card_value(self, card):
        rank = card[:-2] if len(card) > 2 else card[:-1]
        if rank in ['J', 'Q', 'K']:
            return 10
        elif rank == 'A':
            return 11
        else:
            return int(rank)
    
    def hand_value(self, hand):
        value = sum(self.card_value(card) for card in hand)
        aces = sum(1 for card in hand if card[:-2] == 'A' or card[:-1] == 'A')
        while value > 21 and aces:
            value -= 10
            aces -= 1
        return value
    
    @discord.ui.button(label='Hit', style=discord.ButtonStyle.primary)
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        if self.game_over:
            return
        
        self.player_hand.append(self.deck.pop())
        player_value = self.hand_value(self.player_hand)
        
        if player_value > 21:
            self.game_over = True
            for item in self.children:
                item.disabled = True
            
            economy.remove_cash(self.ctx.author.id, self.bet)
            
            embed = discord.Embed(color=0xED4245)
            embed.set_author(name=self.ctx.author.display_name, icon_url=self.ctx.author.display_avatar.url)
            embed.add_field(name="Your Hand", value=f"{' '.join(self.player_hand)}\nValue: {player_value}", inline=False)
            embed.add_field(name="Dealer's Hand", value=f"{' '.join(self.dealer_hand)}\nValue: {self.hand_value(self.dealer_hand)}", inline=False)
            embed.description = f"💥 **BUST!** You lost **${self.bet:,}** 💵!"
            
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            embed = discord.Embed(color=0x5865F2)
            embed.set_author(name=self.ctx.author.display_name, icon_url=self.ctx.author.display_avatar.url)
            embed.add_field(name="Your Hand", value=f"{' '.join(self.player_hand)}\nValue: {player_value}", inline=False)
            embed.add_field(name="Dealer's Hand", value=f"{self.dealer_hand[0]} 🂠", inline=False)
            
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label='Stand', style=discord.ButtonStyle.success)
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        if self.game_over:
            return
        
        self.game_over = True
        for item in self.children:
            item.disabled = True
        
        # Dealer plays
        while self.hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())
        
        player_value = self.hand_value(self.player_hand)
        dealer_value = self.hand_value(self.dealer_hand)
        
        if dealer_value > 21 or player_value > dealer_value:
            profit = self.bet
            economy.add_cash(self.ctx.author.id, profit)
            color = 0x57F287
            result = f"🎉 You won **${profit:,}** 💵!"
        elif player_value == dealer_value:
            color = 0xFEE75C
            result = "**Push!** Your bet is returned."
        else:
            economy.remove_cash(self.ctx.author.id, self.bet)
            color = 0xED4245
            result = f"You lost **${self.bet:,}** 💵!"
        
        embed = discord.Embed(color=color)
        embed.set_author(name=self.ctx.author.display_name, icon_url=self.ctx.author.display_avatar.url)
        embed.add_field(name="Your Hand", value=f"{' '.join(self.player_hand)}\nValue: {player_value}", inline=False)
        embed.add_field(name="Dealer's Hand", value=f"{' '.join(self.dealer_hand)}\nValue: {dealer_value}", inline=False)
        embed.description = result
        
        await interaction.response.edit_message(embed=embed, view=self)


@bot.command(name='bj', aliases=['blackjack'])
async def blackjack(ctx, amount: str):
    """Play blackjack - $bj <amount/all>"""
    if not await casino_channel_only(ctx):
        return
    
    bet = parse_amount(amount, ctx.author.id, use_cash=True)
    
    if bet is None or bet < 10:
        await ctx.send("❌ Minimum bet is $10!")
        return
    
    cash = economy.get_cash(ctx.author.id)
    if cash < bet:
        await ctx.send(f"❌ You don't have enough cash! You currently have ${cash:,} 💵")
        return
    
    view = BlackjackView(ctx, bet)
    
    player_value = view.hand_value(view.player_hand)
    
    if player_value == 21:
        profit = int(bet * 1.5)
        economy.add_cash(ctx.author.id, profit)
        
        embed = discord.Embed(color=0x57F287)
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.add_field(name="Your Hand", value=f"{' '.join(view.player_hand)}\nValue: 21", inline=False)
        embed.add_field(name="Dealer's Hand", value=f"{view.dealer_hand[0]} 🂠", inline=False)
        embed.description = f"🎰 **BLACKJACK!** You won **${profit:,}** 💵!"
        
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(color=0x5865F2)
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.add_field(name="Your Hand", value=f"{' '.join(view.player_hand)}\nValue: {player_value}", inline=False)
        embed.add_field(name="Dealer's Hand", value=f"{view.dealer_hand[0]} 🂠", inline=False)
        
        await ctx.send(embed=embed, view=view)


# ============================================================================
# ROULETTE WITH BUTTONS
# ============================================================================

class RouletteView(View):
    def __init__(self, user, bet):
        super().__init__(timeout=60)
        self.user = user
        self.bet = bet
        
        # Color buttons
        red_btn = Button(label="🔴 Red", style=discord.ButtonStyle.danger, row=0)
        red_btn.callback = self.bet_red
        self.add_item(red_btn)
        
        black_btn = Button(label="⚫ Black", style=discord.ButtonStyle.secondary, row=0)
        black_btn.callback = self.bet_black
        self.add_item(black_btn)
        
        # Odd/Even buttons
        odd_btn = Button(label="Odd", style=discord.ButtonStyle.primary, row=1)
        odd_btn.callback = self.bet_odd
        self.add_item(odd_btn)
        
        even_btn = Button(label="Even", style=discord.ButtonStyle.primary, row=1)
        even_btn.callback = self.bet_even
        self.add_item(even_btn)
        
        # Green/Zero button
        green_btn = Button(label="🟢 0", style=discord.ButtonStyle.success, row=1)
        green_btn.callback = self.bet_zero
        self.add_item(green_btn)
    
    async def spin(self, interaction: discord.Interaction, choice: str, multiplier: int):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        for item in self.children:
            item.disabled = True
        
        # Spinning animation
        embed = discord.Embed(color=0x5865F2)
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.description = "🎡 **Spinning the wheel...**"
        await interaction.response.edit_message(embed=embed, view=self)
        await asyncio.sleep(1.5)
        
        result = random.randint(0, 36)
        reds = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
        blacks = [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35]
        
        won = False
        
        if choice == 'red' and result in reds:
            won = True
        elif choice == 'black' and result in blacks:
            won = True
        elif choice == 'odd' and result % 2 == 1 and result != 0:
            won = True
        elif choice == 'even' and result % 2 == 0 and result != 0:
            won = True
        elif choice == 'zero' and result == 0:
            won = True
        
        if result in reds:
            color_display = "🔴 Red"
        elif result in blacks:
            color_display = "⚫ Black"
        else:
            color_display = "🟢 Green"
        
        if won:
            profit = self.bet * multiplier - self.bet
            economy.add_cash(self.user.id, profit)
            
            embed = discord.Embed(color=0x57F287)
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            embed.description = f"🎡 The ball landed on **{result}** {color_display}\n\n✅ You won **${profit:,}** 💵 (x{multiplier})!"
        else:
            economy.remove_cash(self.user.id, self.bet)
            
            embed = discord.Embed(color=0xED4245)
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            embed.description = f"🎡 The ball landed on **{result}** {color_display}\n\n❌ You lost **${self.bet:,}** 💵!"
        
        await interaction.edit_original_response(embed=embed, view=self)
    
    async def bet_red(self, interaction: discord.Interaction):
        await self.spin(interaction, 'red', 2)
    
    async def bet_black(self, interaction: discord.Interaction):
        await self.spin(interaction, 'black', 2)
    
    async def bet_odd(self, interaction: discord.Interaction):
        await self.spin(interaction, 'odd', 2)
    
    async def bet_even(self, interaction: discord.Interaction):
        await self.spin(interaction, 'even', 2)
    
    async def bet_zero(self, interaction: discord.Interaction):
        await self.spin(interaction, 'zero', 35)


@bot.command(name='roulette')
async def roulette(ctx, amount: str):
    """Play roulette - $roulette <amount>"""
    if not await casino_channel_only(ctx):
        return
    
    bet = parse_amount(amount, ctx.author.id, use_cash=True)
    
    if bet is None or bet < 10:
        await ctx.send("❌ Minimum bet is $10!")
        return
    
    cash = economy.get_cash(ctx.author.id)
    if cash < bet:
        await ctx.send(f"❌ You don't have enough cash! You currently have ${cash:,} 💵")
        return
    
    view = RouletteView(ctx.author, bet)
    
    embed = discord.Embed(color=0x5865F2)
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
    embed.description = f"🎡 **Roulette**\n\nBet: **${bet:,}**\n\nPlace your bet!"
    
    await ctx.send(embed=embed, view=view)


# ============================================================================
# HELP COMMAND
# ============================================================================

@bot.command(name='help')
async def help_command(ctx):
    """Show all commands"""
    user_id = str(ctx.author.id)
    user = economy.get_user(ctx.author.id)
    
    last_help = user.get('last_help')
    now = datetime.now()
    
    if last_help:
        last_help_dt = datetime.fromisoformat(last_help)
        if now - last_help_dt < timedelta(minutes=HELP_COOLDOWN):
            time_left = timedelta(minutes=HELP_COOLDOWN) - (now - last_help_dt)
            seconds = time_left.seconds
            await ctx.send(f"⏱️ Please wait **{seconds}s** before using help again", delete_after=5)
            return
    
    embed = discord.Embed(
        title="🎰 Casino Commands",
        description="All available commands for the casino bot",
        color=0x5865F2
    )
    
    embed.add_field(
        name="💰 Balance Commands",
        value="**$bal [@user]** - Check cash, bank, and total balance\n**$top [cash/bank/total]** - View leaderboard",
        inline=False
    )
    
    embed.add_field(
        name="💵 Earning Commands",
        value="**$work** - Work for money ($4,000-$12,000) [3 min cooldown]\n"
              "**$crime** - Commit a crime ($6,000-$15,000 or fine) [3 min cooldown]\n"
              "**$rob [@user]** - Rob someone [7 min cooldown]\n"
              "**$collect** - Collect reward [12 hour cooldown]\n"
              "**$streak** - Daily streak reward [24 hour cooldown]",
        inline=False
    )
    
    embed.add_field(
        name="💸 Money Transfer",
        value="**$pay [@user] [amount/all]** - Give money to someone\n"
              "**$with [amount/all]** - Withdraw from bank to cash\n"
              "**$dep [amount/all]** - Deposit cash to bank",
        inline=False
    )
    
    embed.add_field(
        name="🎮 Casino Games (Interactive)",
        value="**$mt [amount]** - Mines game (3x5 grid) - Click tiles!\n"
              "**$sm [amount]** - Slot machine - Spin to win!\n"
              "**$bj [amount]** - Blackjack - Hit or stand!\n"
              "**$ht [amount]** - Coinflip - Choose heads or tails!\n"
              "**$roulette [amount]** - Roulette - Bet on colors!\n"
              "**$hl [amount]** - High or low - Guess the card!\n"
              "**$cf [amount]** - Chicken fight - Risk vs reward!\n"
              "**$rps [amount]** - Rock paper scissors!",
        inline=False
    )
    
    if is_admin(ctx):
        embed.add_field(
            name="⚙️ Admin Commands",
            value="**$addmoney [@user] [amount]** - Add money to user\n"
                  "**$removemoney [@user] [amount]** - Remove money from user\n"
                  "**$setmoney [@user] [amount]** - Set user's money",
            inline=False
        )
    
    embed.set_footer(text="Use 'all' instead of amount to bet everything! • All games use interactive buttons!")
    
    economy.data[user_id]['last_help'] = now.isoformat()
    economy.save_data()
    
    await ctx.send(embed=embed)


# ============================================================================
# RUN BOT
# ============================================================================

if __name__ == "__main__":
    # Replace with your bot token
    TOKEN = ''
    bot.run(TOKEN)
