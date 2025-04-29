import os
import json
import asyncio
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')
GUILD_ID = int(os.getenv('GUILD_ID'))
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

streamers = []
live_streams = set()
twitch_access_token = None

STREAMERS_FILE = 'streamers.json'

# Load streamers from file
def load_streamers():
    global streamers
    if os.path.exists(STREAMERS_FILE):
        with open(STREAMERS_FILE, 'r') as f:
            streamers = json.load(f)
    else:
        streamers = []

# Save streamers to file
def save_streamers():
    with open(STREAMERS_FILE, 'w') as f:
        json.dump(streamers, f, indent=4)

async def get_twitch_access_token():
    global twitch_access_token
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        "client_id": TWITCH_CLIENT_ID,
        "client_secret": TWITCH_CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params) as resp:
            data = await resp.json()
            twitch_access_token = data['access_token']

async def check_streamers():
    if not twitch_access_token:
        await get_twitch_access_token()

    url = "https://api.twitch.tv/helix/streams"
    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {twitch_access_token}"
    }

    params = [("user_login", streamer) for streamer in streamers]
    streams_found = set()

    async with aiohttp.ClientSession() as session:
        for i in range(0, len(params), 100):
            async with session.get(url, headers=headers, params=params[i:i+100]) as resp:
                if resp.status == 401:
                    await get_twitch_access_token()
                    return
                data = await resp.json()
                for stream in data.get('data', []):
                    streams_found.add(stream['user_login'])
                    if stream['user_login'] not in live_streams:
                        channel = bot.get_channel(CHANNEL_ID)
                        if channel:
                            embed = discord.Embed(
                                title=f"{stream['user_name']} is LIVE!",
                                url=f"https://twitch.tv/{stream['user_login']}",
                                description=stream['title'],
                                color=discord.Color.purple()
                            )
                            embed.set_thumbnail(url=stream['thumbnail_url'].format(width=1280, height=720))
                            await channel.send(content="@everyone", embed=embed)
    live_streams.clear()
    live_streams.update(streams_found)

@tasks.loop(minutes=5)
async def streamer_check_loop():
    await check_streamers()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    try:
        synced = await tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"Synced {len(synced)} commands to the guild.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    streamer_check_loop.start()

# Slash command to manually recheck
@tree.command(name="recheck", description="Manually recheck streamers", guild=discord.Object(id=GUILD_ID))
async def recheck(interaction: discord.Interaction):
    await check_streamers()
    await interaction.response.send_message("Manual recheck completed!", ephemeral=True)

# Slash command to list streamers
@tree.command(name="liststreamers", description="List all tracked streamers", guild=discord.Object(id=GUILD_ID))
async def liststreamers(interaction: discord.Interaction):
    if not streamers:
        await interaction.response.send_message("No streamers are currently being tracked.")
        return

    streamer_text = "\n".join(streamers)

    if len(streamer_text) <= 2000:
        await interaction.response.send_message(f"Streamers:\n{streamer_text}")
    else:
        chunks = [streamer_text[i:i+1990] for i in range(0, len(streamer_text), 1990)]
        await interaction.response.send_message(f"Streamers:\n{chunks[0]}")
        for chunk in chunks[1:]:
            await interaction.followup.send(f"{chunk}")

# Slash command to add a streamer
@tree.command(name="addstreamer", description="Add a streamer to tracking", guild=discord.Object(id=GUILD_ID))
async def addstreamer(interaction: discord.Interaction, streamer_name: str):
    if streamer_name.lower() in streamers:
        await interaction.response.send_message(f"{streamer_name} is already being tracked.", ephemeral=True)
        return
    streamers.append(streamer_name.lower())
    save_streamers()
    await interaction.response.send_message(f"Added {streamer_name} to the list.", ephemeral=True)

# Slash command to remove a streamer
@tree.command(name="removestreamer", description="Remove a streamer from tracking", guild=discord.Object(id=GUILD_ID))
async def removestreamer(interaction: discord.Interaction, streamer_name: str):
    if streamer_name.lower() not in streamers:
        await interaction.response.send_message(f"{streamer_name} is not being tracked.", ephemeral=True)
        return
    streamers.remove(streamer_name.lower())
    save_streamers()
    await interaction.response.send_message(f"Removed {streamer_name} from the list.", ephemeral=True)

load_streamers()
bot.run(DISCORD_TOKEN)
