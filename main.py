import datetime
import json

import discord
from discord.utils import snowflake_time


class CheckinCheckout(discord.Bot):
    def __init__(self, description=None, *args, **options):
        super().__init__(description, *args, **options)
        self.checkin_time: datetime.datetime
        self.checkout_time: datetime.datetime


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
async def checkout(ctx: discord.ApplicationContext, temp_time):
    final_time = snowflake_time(ctx.interaction.id)
    if bot.checkin_time is not None:
        bot.checkout_time = temp_time + (final_time - bot.checkin_time)
    else:
        bot.checkout_time = temp_time
    await ctx.respond(f"{ctx.author} has checked out \n Time Worked {bot.checkin_time}")


@bot.slash_command(name="break", description="Break")
async def onBreak(ctx: discord.ApplicationContext, temp_time):
    trigger_time = snowflake_time(ctx.interaction.id)
    temp_time = temp_time + (trigger_time - bot.checkin_time)

    await ctx.respond(f"{ctx.author} is on a break ! ")


with open("credentials.json", "r") as file:
    token = json.load(file)["discord_token"]
bot.run(token)
