import os
import json
import random
import aiohttp
import asyncio
import discord
import matplotlib.pyplot as plt
from io import BytesIO
from discord.ext import commands, tasks
from discord.ui import Button, View
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Ensure files exist
if not os.path.exists("user_data.json"):
    with open("user_data.json","w") as f:
        json.dump({}, f)

def load_data(filename):
    with open(filename,"r") as f:
        return json.load(f)

def save_data(filename,data):
    with open(filename,"w") as f:
        json.dump(data,f,indent=4)

def ensure_user(user_id):
    data=load_data("user_data.json")
    uid=str(user_id)
    if uid not in data:
        data[uid]={
            "balance":100,
            "inventory":{},
            "last_daily":None,
            "user_stocks":{},
            "achievements":[],
            "bank":0
        }
        save_data("user_data.json",data)
    return data

def get_balance(user_id):
    data=load_data("user_data.json")
    return data[str(user_id)].get("balance",100)

def update_balance(user_id,amount):
    data=load_data("user_data.json")
    data[str(user_id)]["balance"]+=amount
    save_data("user_data.json",data)

def get_bank(user_id):
    data=load_data("user_data.json")
    return data[str(user_id)]["bank"]

def deposit(user_id,amount):
    data=load_data("user_data.json")
    if data[str(user_id)]["balance"]>=amount:
        data[str(user_id)]["balance"]-=amount
        data[str(user_id)]["bank"]+=amount
        save_data("user_data.json",data)
        return True
    return False

def withdraw(user_id,amount):
    data=load_data("user_data.json")
    if data[str(user_id)]["bank"]>=amount:
        data[str(user_id)]["bank"]-=amount
        data[str(user_id)]["balance"]+=amount
        save_data("user_data.json",data)
        return True
    return False

def user_inventory(user_id):
    data=load_data("user_data.json")
    return data[str(user_id)]["inventory"]

def add_item(user_id,item):
    data=load_data("user_data.json")
    inv=data[str(user_id)]["inventory"]
    if item in inv:
        inv[item]+=1
    else:
        inv[item]=1
    save_data("user_data.json",data)

shop_items = {
    "apple":{"price":10,"description":"A tasty apple."},
    "book":{"price":20,"description":"A knowledge-filled book."},
    "sword":{"price":100,"description":"A sword to show off your wealth."}
}

# NASDAQ-like stocks
STOCK_SYMBOLS = ["AAPL","MSFT","AMZN","GOOGL","TSLA","NFLX","NVDA","META"]
STOCK_PRICES = {symbol: random.uniform(100,500) for symbol in STOCK_SYMBOLS}
PRICE_HISTORY = {symbol:[STOCK_PRICES[symbol]] for symbol in STOCK_SYMBOLS}

@tasks.loop(minutes=1)
async def update_stock_prices():
    for symbol in STOCK_SYMBOLS:
        change = random.uniform(-5,5)
        new_price = max(1,STOCK_PRICES[symbol]+change)
        STOCK_PRICES[symbol]=round(new_price,2)
        PRICE_HISTORY[symbol].append(round(new_price,2))
    # Print to console for debug
    print("Stock prices updated.")

def generate_stock_chart(symbol):
    plt.figure(figsize=(6,4))
    plt.plot(PRICE_HISTORY[symbol], marker='o', color='blue', linestyle='-')
    plt.title(f"{symbol} Price Chart")
    plt.xlabel("Time Steps")
    plt.ylabel("Price (USD)")
    plt.grid(True)
    buf=BytesIO()
    plt.savefig(buf,format='png')
    buf.seek(0)
    plt.close()
    return buf

async def fetch_riddle():
    url="https://riddles-api.vercel.app/random"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status==200:
                data=await resp.json()
                riddle=data.get("riddle","No riddle")
                answer=data.get("answer","No answer")
                return riddle,answer
            return "Could not fetch a riddle.",""

@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")
    update_stock_prices.start()

@bot.command()
async def balance(ctx):
    ensure_user(ctx.author.id)
    bal=get_balance(ctx.author.id)
    bank_amt=get_bank(ctx.author.id)
    await ctx.send(f"Your balance: {bal} coins in hand, {bank_amt} in bank.")

@bot.command()
async def daily(ctx):
    data=ensure_user(ctx.author.id)
    user_id=str(ctx.author.id)
    ld=data[user_id]["last_daily"]
    now=datetime.utcnow()
    if ld:
        old=datetime.fromisoformat(ld)
        if now-old<timedelta(hours=24):
            await ctx.send("You have already claimed your daily reward today!")
            return
    reward=50
    data[user_id]["balance"]+=reward
    data[user_id]["last_daily"]=now.isoformat()
    save_data("user_data.json",data)
    await ctx.send(f"You claimed your daily {reward} coins!")

@bot.command()
async def work(ctx):
    ensure_user(ctx.author.id)
    earnings=random.randint(20,50)
    update_balance(ctx.author.id,earnings)
    await ctx.send(f"You worked hard and earned {earnings} coins!")

@bot.command()
async def deposit(ctx,amount:int):
    ensure_user(ctx.author.id)
    if amount<=0:
        await ctx.send("Invalid amount.")
        return
    if deposit(ctx.author.id,amount):
        await ctx.send(f"You deposited {amount} coins into your bank.")
    else:
        await ctx.send("Not enough coins in hand.")

@bot.command()
async def withdraw(ctx,amount:int):
    ensure_user(ctx.author.id)
    if amount<=0:
        await ctx.send("Invalid amount.")
        return
    if withdraw(ctx.author.id,amount):
        await ctx.send(f"You withdrew {amount} coins from your bank.")
    else:
        await ctx.send("Not enough coins in the bank.")

@bot.command()
async def gift(ctx, user:discord.User, amount:int):
    ensure_user(ctx.author.id)
    ensure_user(user.id)
    if amount<=0:
        await ctx.send("Invalid amount.")
        return
    bal=get_balance(ctx.author.id)
    if bal<amount:
        await ctx.send("You don't have enough coins.")
        return
    update_balance(ctx.author.id,-amount)
    update_balance(user.id,amount)
    await ctx.send(f"You gifted {amount} coins to {user.mention}!")

@bot.command()
async def leaderboard_coins(ctx):
    data=load_data("user_data.json")
    arr=[]
    for uid,udata in data.items():
        arr.append((int(uid),udata["balance"]))
    arr.sort(key=lambda x:x[1],reverse=True)
    desc=""
    for i,(uid,bal) in enumerate(arr[:10]):
        user=bot.get_user(uid)
        name=user.name if user else f"User {uid}"
        desc+=f"{i+1}. {name}: {bal} coins\n"
    embed=discord.Embed(title="🏆 Coin Leaderboard",description=desc,color=0xFFD700)
    await ctx.send(embed=embed)

@bot.command()
async def shop(ctx):
    desc=""
    for item,info in shop_items.items():
        desc+=f"**{item}** - {info['price']} coins: {info['description']}\n"
    embed=discord.Embed(title="🛒 Shop",description=desc,color=0x00FF00)
    await ctx.send(embed=embed)

@bot.command()
async def buy(ctx, item:str):
    ensure_user(ctx.author.id)
    item=item.lower()
    if item not in shop_items:
        await ctx.send("That item doesn't exist.")
        return
    price=shop_items[item]["price"]
    bal=get_balance(ctx.author.id)
    if bal<price:
        await ctx.send("Not enough coins.")
        return
    update_balance(ctx.author.id,-price)
    add_item(ctx.author.id,item)
    await ctx.send(f"You bought a {item} for {price} coins.")

@bot.command()
async def inventory(ctx):
    ensure_user(ctx.author.id)
    inv=user_inventory(ctx.author.id)
    if not inv:
        await ctx.send("Your inventory is empty.")
        return
    msg=""
    for i,a in inv.items():
        msg+=f"{i}: x{a}\n"
    await ctx.send(msg)

@bot.command()
async def stock(ctx,symbol:str):
    symbol=symbol.upper()
    if symbol in STOCK_SYMBOLS:
        price=STOCK_PRICES[symbol]
        await ctx.send(f"{symbol} current price: ${price}")
    else:
        await ctx.send("Invalid stock symbol.")

@bot.command()
async def chart(ctx,symbol:str):
    symbol=symbol.upper()
    if symbol in STOCK_SYMBOLS:
        buf=generate_stock_chart(symbol)
        file=discord.File(buf,filename="chart.png")
        embed=discord.Embed(title=f"{symbol} Chart",color=0x3498DB)
        embed.set_image(url="attachment://chart.png")
        await ctx.send(file=file,embed=embed)
    else:
        await ctx.send("Invalid stock symbol.")

@bot.command()
async def riddle(ctx):
    riddle,answer=await fetch_riddle()
    # Show a button to reveal the answer
    class RiddleView(View):
        def __init__(self, ans):
            super().__init__(timeout=60)
            self.ans=ans
        @discord.ui.button(label="Show Answer",style=discord.ButtonStyle.secondary)
        async def show_answer(self,interaction,button):
            await interaction.response.send_message(f"The answer is: **{self.ans}**",ephemeral=True)

    await ctx.send(f"**Riddle:** {riddle}",view=RiddleView(answer))

@bot.command()
async def about(ctx):
    embed=discord.Embed(title="About This Bot",description="This is a super interactive, polished, and popular bot!")
    embed.set_image(url="https://cdn.discordapp.com/avatars/1283498484749566077/9f49661313873f7b653507bcf08361d2.png?size=4096")
    await ctx.send(embed=embed)

@bot.command()
async def meme_buttons(ctx):
    # Just mock memes (no API for memes given)
    memes=[
        {"name":"Funny Cat","url":"https://cataas.com/cat"},
        {"name":"Smiling Dog","url":"https://placedog.net/500?random"},
        {"name":"Random Meme","url":"https://http.cat/404"}
    ]
    index=[0]

    class MemeView(View):
        def __init__(self):
            super().__init__(timeout=120)
            self.update_buttons()

        def update_buttons(self):
            self.children[0].disabled=(index[0]==0)
            self.children[1].disabled=(index[0]==len(memes)-1)

        @discord.ui.button(label="Prev",style=discord.ButtonStyle.primary,disabled=True)
        async def prev_btn(self,interaction,button):
            index[0]-=1
            self.update_buttons()
            embed=discord.Embed(title=memes[index[0]]["name"])
            embed.set_image(url=memes[index[0]]["url"])
            await interaction.response.edit_message(embed=embed,view=self)

        @discord.ui.button(label="Next",style=discord.ButtonStyle.primary)
        async def next_btn(self,interaction,button):
            index[0]+=1
            self.update_buttons()
            embed=discord.Embed(title=memes[index[0]]["name"])
            embed.set_image(url=memes[index[0]]["url"])
            await interaction.response.edit_message(embed=embed,view=self)

    embed=discord.Embed(title=memes[index[0]]["name"])
    embed.set_image(url=memes[index[0]]["url"])
    await ctx.send(embed=embed,view=MemeView())

@bot.command()
async def rps(ctx):
    # Interactive RPS with buttons
    class RPSView(View):
        def __init__(self):
            super().__init__(timeout=30)

        @discord.ui.button(label="Rock",style=discord.ButtonStyle.primary)
        async def rock_btn(self,interaction,button):
            await self.play(interaction,"rock")

        @discord.ui.button(label="Paper",style=discord.ButtonStyle.primary)
        async def paper_btn(self,interaction,button):
            await self.play(interaction,"paper")

        @discord.ui.button(label="Scissors",style=discord.ButtonStyle.primary)
        async def scissors_btn(self,interaction,button):
            await self.play(interaction,"scissors")

        async def play(self,interaction,choice):
            bot_choice=random.choice(["rock","paper","scissors"])
            if bot_choice==choice:
                await interaction.response.send_message(f"I chose {bot_choice}. It's a tie!",ephemeral=True)
            elif (choice=="rock" and bot_choice=="scissors") or (choice=="scissors" and bot_choice=="paper") or (choice=="paper" and bot_choice=="rock"):
                await interaction.response.send_message(f"I chose {bot_choice}. You win!",ephemeral=True)
            else:
                await interaction.response.send_message(f"I chose {bot_choice}. You lose!",ephemeral=True)
            self.stop()

    await ctx.send("Choose your move:",view=RPSView())

@bot.command()
async def what(ctx):
    # Paginated command list with UI
    pages = [
        {
            "title":"Economy Commands",
            "fields":[
                ("!balance","Check your coin & bank balance"),
                ("!daily","Claim daily reward"),
                ("!work","Earn coins by working"),
                ("!deposit <amount>","Deposit coins to bank"),
                ("!withdraw <amount>","Withdraw coins from bank"),
                ("!gift <@user> <amount>","Gift coins to another user"),
                ("!shop","View items in shop"),
                ("!buy <item>","Buy an item from the shop"),
                ("!inventory","View your inventory"),
                ("!leaderboard_coins","Show top coin holders")
            ],
            "color":0x00FF00
        },
        {
            "title":"Stocks & Riddles & Fun",
            "fields":[
                ("!stock <symbol>","Check a stock price"),
                ("!chart <symbol>","View a stock price chart"),
                ("!riddle","Get a random riddle with a button to show answer"),
                ("!meme_buttons","Browse memes with Next/Prev buttons"),
                ("!rps","Play Rock-Paper-Scissors with interactive buttons"),
                ("!about","About this bot with an image")
            ],
            "color":0x3498DB
        },
        {
            "title":"Utilities & Info",
            "fields":[
                ("!what","Show this command menu"),
                ("!about","Show about info and image"),
                ("!serverinfo","Show server info"),
                ("!userinfo [@user]","Show user info"),
                ("!invite","Show bot invite link")
            ],
            "color":0x9B59B6
        }
    ]

    class WhatView(View):
        def __init__(self):
            super().__init__(timeout=120)
            self.index=0
            self.update_buttons()

        def update_buttons(self):
            for child in self.children:
                if isinstance(child,Button):
                    if child.custom_id=="prev":
                        child.disabled=(self.index==0)
                    elif child.custom_id=="next":
                        child.disabled=(self.index==len(pages)-1)

        def get_embed(self):
            page=pages[self.index]
            embed=discord.Embed(title=page["title"],color=page["color"])
            for name,value in page["fields"]:
                embed.add_field(name=name,value=value,inline=False)
            embed.set_footer(text=f"Page {self.index+1}/{len(pages)}")
            return embed

        @discord.ui.button(label="Previous",style=discord.ButtonStyle.primary,custom_id="prev")
        async def prev_button(self,interaction,button):
            self.index-=1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(),view=self)

        @discord.ui.button(label="Next",style=discord.ButtonStyle.primary,custom_id="next")
        async def next_button(self,interaction,button):
            self.index+=1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(),view=self)

    view=WhatView()
    await ctx.send(embed=view.get_embed(),view=view)

@bot.command()
async def serverinfo(ctx):
    g=ctx.guild
    embed=discord.Embed(title="Server Info",description=f"Name: {g.name}\nMembers: {len(g.members)}",color=0x1ABC9C)
    await ctx.send(embed=embed)

@bot.command()
async def userinfo(ctx,user:discord.User=None):
    if user is None:
        user=ctx.author
    embed=discord.Embed(title=f"{user.name}'s Info",description=f"ID: {user.id}",color=0x2ECC71)
    embed.set_thumbnail(url=user.avatar.url if user.avatar else "")
    await ctx.send(embed=embed)

@bot.command()
async def invite(ctx):
    await ctx.send("Invite me to your server: [Invite Link](https://discord.com)")

bot.run(TOKEN)
