import os
import json
import aiohttp
import asyncio
import discord
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Grab secrets
TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID'))
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))

# Create bot instance
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Global variables
access_token = None
announced_streamers = set()

# Get Twitch access token
async def get_access_token():
    global access_token
    url = 'https://id.twitch.tv/oauth2/token'
    params = {
        'client_id': TWITCH_CLIENT_ID,
        'client_secret': TWITCH_CLIENT_SECRET,
        'grant_type': 'client_credentials'
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params) as resp:
            data = await resp.json()
            access_token = data['access_token']

# Check if streamer is live
async def is_streamer_live(streamer_name):
    url = f"https://api.twitch.tv/helix/streams?user_login={streamer_name}"
    headers = {
        'Client-ID': TWITCH_CLIENT_ID,
        'Authorization': f'Bearer {access_token}'
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()
            if data['data']:
                return data['data'][0]
            else:
                return None

# Send rich live announcement
async def send_live_announcement(stream_info):
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        print("Channel not found!")
        return

    streamer_name = stream_info['user_name']
    stream_title = stream_info['title']
    game_name = stream_info.get('game_name', 'Unknown Game')
    viewer_count = stream_info.get('viewer_count', 0)
    thumbnail_url = stream_info['thumbnail_url'].format(width=1280, height=720)
    stream_url = f"https://twitch.tv/{stream_info['user_login']}"

    embed = discord.Embed(
        title=f"{streamer_name} is now LIVE!",
        url=stream_url,
        description=f"🔥 *Playing* **{game_name}**\n👥 **Viewers:** {viewer_count}\n\n**{stream_title}**",
        color=discord.Color.purple()
    )
    embed.set_image(url=thumbnail_url)
    embed.set_footer(text="Powered by V1ewerbot 🚀")

    await channel.send(embed=embed)

# Background loop to check streamers
@tasks.loop(minutes=10)
async def check_streamers():
    global announced_streamers

    try:
        with open('streamers.json', 'r') as f:
            streamers = json.load(f)
    except Exception as e:
        print(f"Error reading streamers.json: {e}")
        return

    for streamer in streamers:
        stream_info = await is_streamer_live(streamer)
        if stream_info and streamer not in announced_streamers:
            await send_live_announcement(stream_info)
            announced_streamers.add(streamer)
        elif not stream_info and streamer in announced_streamers:
            announced_streamers.remove(streamer)

# Slash Command: /addstreamer (Admin Only)
@bot.tree.command(name="addstreamer", description="Add a Twitch streamer to the list", guild=discord.Object(id=GUILD_ID))
async def add_streamer(interaction: discord.Interaction, streamer_name: str):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    try:
        with open('streamers.json', 'r') as f:
            streamers = json.load(f)
    except Exception:
        streamers = []

    if streamer_name.lower() in [s.lower() for s in streamers]:
        await interaction.response.send_message(f"{streamer_name} is already in the list.", ephemeral=True)
        return

    streamers.append(streamer_name)
    with open('streamers.json', 'w') as f:
        json.dump(streamers, f, indent=4)

    await interaction.response.send_message(f"✅ Added {streamer_name} to the watch list!", ephemeral=True)

# Slash Command: /removestreamer (Admin Only)
@bot.tree.command(name="removestreamer", description="Remove a Twitch streamer from the list", guild=discord.Object(id=GUILD_ID))
async def remove_streamer(interaction: discord.Interaction, streamer_name: str):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    try:
        with open('streamers.json', 'r') as f:
            streamers = json.load(f)
    except Exception:
        streamers = []

    updated_streamers = [s for s in streamers if s.lower() != streamer_name.lower()]

    if len(updated_streamers) == len(streamers):
        await interaction.response.send_message(f"{streamer_name} was not found in the list.", ephemeral=True)
        return

    with open('streamers.json', 'w') as f:
        json.dump(updated_streamers, f, indent=4)

    await interaction.response.send_message(f"✅ Removed {streamer_name} from the watch list.", ephemeral=True)

# Slash Command: /liststreamers (Open to everyone)
@bot.tree.command(name="liststreamers", description="List all tracked Twitch streamers", guild=discord.Object(id=GUILD_ID))
async def list_streamers(interaction: discord.Interaction):
    try:
        with open('streamers.json', 'r') as f:
            streamers = json.load(f)
    except Exception:
        streamers = []

    if not streamers:
        await interaction.response.send_message("No streamers currently being tracked.", ephemeral=True)
    else:
        streamer_list = "\n".join(f"- {s}" for s in streamers)
        await interaction.response.send_message(f"🎥 Currently tracking:\n{streamer_list}", ephemeral=True)

# When bot is ready
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")

    # Set custom status
    activity = discord.Activity(type=discord.ActivityType.watching, name="Twitch streams 👀")
    await bot.change_presence(activity=activity)

    # Sync slash commands
    try:
        await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print("Slash commands synced successfully.")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")

    await get_access_token()
    check_streamers.start()

# Main entry point
if __name__ == "__main__":
    print("Starting V1ewerbot...")
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"Error starting bot: {e}")
