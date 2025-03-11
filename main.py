import asyncio
import json
import aiohttp
import subprocess
import discord
from discord.ext import commands
from datetime import datetime, timedelta
import pytz  # Import pytz for timezone support

# Load configuration from JSON file
with open('config.json') as f:
    config = json.load(f)

# Discord bot settings
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='', intents=intents)

# Configuration variables
nChannel = config["notifyChannel"]  # Discord channel ID
nSurvivor = config["warga"]  # Role ID to mention
panel = config["panel_url"]
server_id = config["server_id"]
ApiKey = config["apikey"]
ip_address = config["IP_ADDRESS"]
password = config["PASSWORD_RCON"]
botToken = config["botToken"]

# Set timezone to GMT+8 (Asia/Singapore)
TZ = pytz.timezone("Asia/Singapore")

# Scheduled restart times (GMT+8)
RESTART_TIMES = [(0, 30), (6, 30), (12, 30), (18, 30)]  # 12:30 AM, 6:30 AM, 12:30 PM, 6:30 PM

async def send_message(message):
    """Send a message to the configured Discord channel."""
    channel = bot.get_channel(nChannel)
    if channel:
        await channel.send(f"<@&{nSurvivor}> {message}")
    else:
        print("Channel not found!")

async def send_ingame_message(message, save=True):
    """Send a message to the game server via RCON, and optionally run 'save'."""
    command = f"./rcon -a {ip_address} -p {password} \"servermsg \\\"{message}\\\"\""
    subprocess.run(command, shell=True, check=True)

    if save:
        save_command = f"./rcon -a {ip_address} -p {password} \"save\""
        subprocess.run(save_command, shell=True, check=True)

async def restart_server():
    """Send a restart command to the server via Pterodactyl API."""
    url = f"{panel}api/client/servers/{server_id}/power"
    headers = {
        'Accept': 'application/json',
        'content-type': 'application/json',
        'Authorization': f'Bearer {ApiKey}'
    }
    payload = {"signal": "restart"}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            print("Server Restart HTTP Status Code:", response.status)

async def check_server_status():
    """Check if the server is online after restart."""
    url = f"{panel}api/client/servers/{server_id}/resources"
    headers = {
        'Accept': 'application/json',
        'content-type': 'application/json',
        'Authorization': f'Bearer {ApiKey}'
    }
    
    async with aiohttp.ClientSession() as session:
        while True:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("attributes", {}).get("current_state", "N/A") == 'running':
                        return True
            await asyncio.sleep(30)  # Check every 30 seconds

async def schedule_restart():
    """Handles scheduled restarts with countdown messages in GMT+8."""
    while True:
        now = datetime.now(TZ)  # Get current time in GMT+8
        for hour, minute in RESTART_TIMES:
            restart_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            if restart_time < now:
                restart_time += timedelta(days=1)  # Move to the next day if the time has passed
            
            wait_time = (restart_time - now).total_seconds()
            print(f"Next restart scheduled at: {restart_time} (in {wait_time} seconds)")
            await asyncio.sleep(wait_time - 1800)  # Wait until 30 min before restart
            
            # Countdown messages with "save" after each
            for msg, delay in [("30 minutes", 900), ("15 minutes", 600), ("5 minutes", 240), ("1 minute", 60)]:
                await send_message(f"Server will restart in {msg}!")
                await send_ingame_message(f"Server will restart in {msg}!", save=True)  # Save after each message
                await asyncio.sleep(delay)

            # Restart the server
            await send_message("Restarting server now!")
            await send_ingame_message("Restarting server now!", save=True)
            await restart_server()
            
            # Wait until server is back online
            if await check_server_status():
                await send_message("Server is back online!")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.loop.create_task(schedule_restart())

bot.run(botToken)
