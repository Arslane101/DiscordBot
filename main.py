import datetime
import json
import os
import threading
import time

import discord
from discord.utils import snowflake_time
from flask import Flask


class CheckinCheckout(discord.Bot):
    def __init__(self, description=None, *args, **options):
        super().__init__(description, *args, **options)
        self.checkin_time: datetime.datetime
        self.checkout_time: datetime.datetime
        self.total: datetime.datetime


bot = CheckinCheckout()
temp_time = 0


@bot.event
async def on_ready():
    print(f"{bot.user} is ready and online!")


@bot.slash_command(name="hello", description="Say hello to the bot")
async def hello(ctx: discord.ApplicationContext):
    await ctx.respond("Hey!")


# Checkin and start counting the time
@bot.slash_command(name="checkin", description="Check-in")
async def checkin(ctx: discord.ApplicationContext):
    await ctx.respond(f"{ctx.author} has checked in")
    trigger_time = snowflake_time(ctx.interaction.id)
    bot.checkin_time = trigger_time


@bot.slash_command(name="checkout", description="Check-out")
async def checkout(ctx: discord.ApplicationContext):
    final_time = snowflake_time(ctx.interaction.id)
    if bot.checkin_time is not None:
        bot.checkout_time = bot.total + (final_time - bot.checkin_time)
    else:
        bot.checkout_time = bot.total
    await ctx.respond(f"{ctx.author} has checked out \n Time Worked {bot.checkin_time}")


@bot.slash_command(name="break", description="Break")
async def onBreak(ctx: discord.ApplicationContext):
    trigger_time = snowflake_time(ctx.interaction.id)
    bot.total = bot.total + (trigger_time - bot.checkin_time)

    await ctx.respond(f"{ctx.author} is on a break ! ")


if os.path.exists("credentials.json"):
    with open("credentials.json") as f:
        creds = json.load(f)
        token = creds.get("discord_token")
else:
    token = os.getenv("DISCORD_TOKEN")

app = Flask(__name__)


@app.route("/")
def home():
    return "Bot is running!"


time.sleep(15)
threading.Thread(daemon=True, target=lambda: app.run(host="0.0.0.0", port=8080)).start()


bot.run(token)
