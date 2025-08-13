import os
import textwrap
from dotenv import load_dotenv
from together import Together
import discord
from discord.ext import commands
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# Simple healthcheck server (works in Python 3.12)
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

def start_health_server():
    server = HTTPServer(("0.0.0.0", 8080), HealthHandler)
    server.serve_forever()

Thread(target=start_health_server, daemon=True).start()

# Load env
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
client = Together(api_key=os.getenv("TOGETHER_API_KEY"))

BOT_PREFIX = '.'

# Load custom prompt from evelyn.txt
def load_custom_prompt():
    try:
        with open("evelyn.txt", "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        print(f"Error loading prompt file: {e}")
        return ""

# AI response function
def get_ai_response(prompt):
    try:
        response = client.chat.completions.create(
            model="meta-llama/Llama-3-70b-chat-hf",
            messages=[
                {"role": "system", "content": load_custom_prompt()},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=100
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"AI Error: {e}")
        return "oops something broke lol"

# Cog for AI chat in specific channels
class AIChannelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.enabled_channels = set()
        self.message_context = {}

    @commands.command(name="set")
    async def set_channel(self, ctx):
        channel = ctx.channel
        if channel.id in self.enabled_channels:
            await ctx.send(f"aichat already enabled in {channel.mention}")
        else:
            self.enabled_channels.add(channel.id)
            await ctx.send(f"aichat enabled in {channel.mention}")

    @commands.command(name="unset")
    async def unset_channel(self, ctx):
        channel = ctx.channel
        if channel.id not in self.enabled_channels:
            await ctx.send(f"aichat not enabled in {channel.mention}")
        else:
            self.enabled_channels.remove(channel.id)
            await ctx.send(f"aichat disabled in {channel.mention}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if message.channel.id not in self.enabled_channels:
            return
        if message.content.startswith(BOT_PREFIX):
            return

        # Check if message is a reply to bot or mentions bot
        replied_msg = None
        if message.reference and message.reference.message_id:
            try:
                replied_msg = await message.channel.fetch_message(message.reference.message_id)
            except Exception:
                pass

        is_reply_to_bot = replied_msg and replied_msg.author.id == self.bot.user.id
        is_mentioning_bot = self.bot.user in message.mentions

        if not (is_reply_to_bot or is_mentioning_bot):
            return

        original_prompt = None
        if is_reply_to_bot and message.reference.message_id in self.message_context:
            original_prompt = self.message_context[message.reference.message_id]

        combined_prompt = message.content
        if original_prompt:
            combined_prompt = f"{original_prompt}\n\nuser reply: {message.content}"

        reply_text = get_ai_response(combined_prompt)

        bot_msg = await message.reply(reply_text)
        self.message_context[bot_msg.id] = original_prompt if original_prompt else message.content

# Main bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")

async def main():
    async with bot:
        await bot.add_cog(AIChannelCog(bot))
        await bot.start(DISCORD_TOKEN)

import asyncio
asyncio.run(main())