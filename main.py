import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import os
import json
import asyncio

TOKEN = os.getenv("DISCORD_TOKEN")

# ----------------------- CONFIG -----------------------

GUILD_MEMBER_ROLE_ID = 1473906476904087654
BANANITE_MEMBER_ROLE_ID = 1449956320051597435

EMOJI_SWORDS = "<:swords:1474004803146223638>"
EMOJI_DISCORD = "<:discord:1473994882443120735>"
EMOJI_ROBLOX = "<:roblox:1473995225272946800>"

DB_FILE = "usernames.json"

# ----------------------- BOT SETUP -----------------------

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ----------------------- DATABASE -----------------------

def load_usernames():
    if not os.path.isfile(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_usernames(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ----------------------- ROBLOX API -----------------------

async def get_roblox_avatar(username: str):
    async with aiohttp.ClientSession() as session:
        url = "https://users.roblox.com/v1/usernames/users"
        payload = {"usernames": [username], "excludeBannedUsers": True}

        async with session.post(url, json=payload) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            if not data.get("data"):
                return None
            roblox_id = data["data"][0]["id"]

        avatar_url = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={roblox_id}&size=420x420&format=Png&isCircular=false"

        async with session.get(avatar_url) as resp:
            if resp.status != 200:
                return None
            avatar_data = await resp.json()
            if avatar_data.get("data"):
                return avatar_data["data"][0]["imageUrl"]

    return None

# ----------------------- COMMANDS -----------------------

@bot.tree.command(name="set_roblox_username", description="Set your Roblox username")
@app_commands.describe(username="Your Roblox username")
async def set_roblox_username(interaction: discord.Interaction, username: str):

    avatar = await get_roblox_avatar(username)

    if not avatar:
        await interaction.response.send_message(
            f"❌ Roblox username `{username}` not found.",
            ephemeral=True
        )
        return

    data = load_usernames()
    data[str(interaction.user.id)] = username
    save_usernames(data)

    await interaction.response.send_message(
        f"✅ Your Roblox username has been set to `{username}`",
        ephemeral=True
    )


@bot.tree.command(name="profile", description="View your/a user's profile")
@app_commands.describe(user="Select a user")
async def profile(interaction: discord.Interaction, user: discord.Member):

    data = load_usernames()
    roblox_username = data.get(str(user.id))

    # ---------------- Guild Role Detection ----------------

    guild_role = None

    if discord.utils.get(user.roles, id=GUILD_MEMBER_ROLE_ID):
        guild_role = user.guild.get_role(GUILD_MEMBER_ROLE_ID)

    elif discord.utils.get(user.roles, id=BANANITE_MEMBER_ROLE_ID):
        guild_role = user.guild.get_role(BANANITE_MEMBER_ROLE_ID)

    if guild_role:
        guild_status = guild_role.mention
        role_color = guild_role.color
    else:
        guild_status = "No Guild Role"
        role_color = discord.Color.greyple()

    # ---------------- Avatar Logic ----------------

    avatar_url = user.display_avatar.url

    if roblox_username:
        roblox_avatar = await get_roblox_avatar(roblox_username)
        if roblox_avatar:
            avatar_url = roblox_avatar
        else:
            await interaction.response.send_message(
                f"❌ Roblox username `{roblox_username}` not found.",
                ephemeral=True
            )
            return

    # ---------------- Embed Layout ----------------

    embed = discord.Embed(
        title=f"{user.display_name}'s Profile",
        color=role_color,
        description=f"{EMOJI_SWORDS} **Current Rank:** {guild_status}"  # Rank line right under title
    )

    # Top line (Discord avatar + username)
    embed.set_author(
        name=user.name,
        icon_url=user.display_avatar.url
    )

    # Thumbnail (Roblox avatar if set, else Discord avatar)
    embed.set_thumbnail(url=avatar_url)

    # Discord + Roblox SAME LINE (inline)
    embed.add_field(
        name=f"{EMOJI_DISCORD} Discord",
        value=user.mention,
        inline=True
    )

    embed.add_field(
        name=f"{EMOJI_ROBLOX} Roblox",
        value=roblox_username if roblox_username else "Not set",
        inline=True
    )

    # Footer
    embed.set_footer(text="Bananite Guild Bot 🍌")

    await interaction.response.send_message(embed=embed)

# ----------------------- STATUS ROTATION -----------------------

statuses = [
    discord.Game(name="Join Bananite Guild 🍌"),
    discord.Game(name="discord.gg/bananite")
]

@tasks.loop(seconds=30)
async def rotate_status():
    for status in statuses:
        await bot.change_presence(status=discord.Status.dnd, activity=status)
        await asyncio.sleep(30)

@bot.event
async def on_ready():
    await bot.tree.sync()
    rotate_status.start()
    print(f"Logged in as {bot.user}")

# ----------------------- RUN -----------------------

bot.run(TOKEN)
