import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import View, Button
import io
import aiohttp
import os
import json
import asyncio
import subprocess

TOKEN = os.getenv("DISCORD_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")  # format: username/repo

# ----------------------- CONFIG -----------------------

GUILD_MEMBER_ROLE_ID = 1473906476904087654
BANANITE_MEMBER_ROLE_ID = 1449956320051597435
WELCOME_CHANNEL_ID = 1474036479855431757
WELCOME_IMAGE_URL = "https://media1.tenor.com/m/TSVpYwvM-s8AAAAd/xxiisoul-thanos.gif"
GOODBYE_IMAGE_URL = "https://media1.tenor.com/m/eARfzQt-NhQAAAAd/far-cry6-laugh.gif"

EMOJI_SWORDS = "<:swords:1474004803146223638>"
EMOJI_DISCORD = "<:discord:1473994882443120735>"
EMOJI_ROBLOX = "<:roblox:1473995225272946800>"

DB_FILE = "usernames.json"
GUILD_ID = 1449955287682514976

# ----------------------- BOT SETUP -----------------------

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

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

# ----------------------- GITHUB PUSH -----------------------

def push_to_github(commit_message):
    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("❌ GitHub token or repo not set.")
        return

    try:
        subprocess.run(
            f"git remote set-url origin https://{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git",
            shell=True
        )

        subprocess.run("git checkout -B main", shell=True)
        subprocess.run("git add usernames.json", shell=True)

        commit = subprocess.run(
            f'git commit -m "{commit_message}"',
            shell=True,
            capture_output=True,
            text=True
        )

        if "nothing to commit" in commit.stdout.lower():
            print("⚠️ Nothing to commit.")
            return

        subprocess.run("git pull origin main --rebase", shell=True)
        subprocess.run("git push origin main", shell=True)

        print("✅ GitHub push successful.")

    except Exception as e:
        print(f"GitHub push error: {e}")

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
    push_to_github(f"Update Roblox username for {interaction.user.name}")

    await interaction.response.send_message(
        f"✅ Your Roblox username has been set to `{username}`",
        ephemeral=True
    )

@bot.tree.command(name="profile", description="View your/a user's profile")
@app_commands.describe(user="Select a user")
async def profile(interaction: discord.Interaction, user: discord.Member):

    data = load_usernames()
    roblox_username = data.get(str(user.id))

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

    avatar_url = user.display_avatar.url

    if roblox_username:
        roblox_avatar = await get_roblox_avatar(roblox_username)
        if roblox_avatar:
            avatar_url = roblox_avatar

    embed = discord.Embed(
        title=f"{user.display_name}'s Profile",
        color=role_color,
        description=f"{EMOJI_SWORDS} **Current Rank:** {guild_status}"
    )

    embed.set_author(name=user.name, icon_url=user.display_avatar.url)
    embed.set_thumbnail(url=avatar_url)

    embed.add_field(name=f"{EMOJI_DISCORD} Discord", value=user.mention, inline=True)
    embed.add_field(name=f"{EMOJI_ROBLOX} Roblox",
                    value=roblox_username if roblox_username else "Not set",
                    inline=True)

    embed.set_footer(text="Bananite Guild Bot 🍌")

    await interaction.response.send_message(embed=embed)

# ======================== CREW INFO ==================

@bot.tree.command(name="crew_info", description="Show a list of all Guild Crew members (paginated)")
async def crew_info(interaction: discord.Interaction):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ Could not find the guild.", ephemeral=True)
        return

    role = guild.get_role(GUILD_MEMBER_ROLE_ID)
    if not role:
        await interaction.response.send_message("❌ Guild Crew role not found.", ephemeral=True)
        return

    data = load_usernames()

    members_list = [
        (member, data.get(str(member.id), "Not set"))
        for member in role.members
        if not member.bot
    ]

    if not members_list:
        await interaction.response.send_message("❌ No members found in Guild Crew.", ephemeral=True)
        return

    total_members = len(members_list)

    PAGE_SIZE = 8
    pages = [members_list[i:i + PAGE_SIZE] for i in range(0, len(members_list), PAGE_SIZE)]
    total_pages = len(pages)

    def create_embed(page_index: int):
        embed = discord.Embed(
            title=f"{EMOJI_SWORDS} Bananite Guild Crew",
            color=role.color
        )

        embed.description = (
            f"**Total Crew Members:** `{total_members}`\n"
            f"━━━━━━━━━━━━━━━━━━"
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        discord_column = []
        roblox_column = []

        for member, roblox in pages[page_index]:
            discord_column.append(f"{member.mention}")
            roblox_column.append(f"`{roblox}`")

        embed.add_field(name=f"{EMOJI_DISCORD} Discord",
                        value="\n".join(discord_column),
                        inline=True)

        embed.add_field(name=f"{EMOJI_ROBLOX} Roblox",
                        value="\n".join(roblox_column),
                        inline=True)

        embed.set_footer(
            text=f"Bananite Guild Bot 🍌 • Page {page_index+1}/{total_pages}"
        )

        return embed

    current_page = 0
    embed = create_embed(current_page)

    if total_pages == 1:
        await interaction.response.send_message(embed=embed)
        return

    class CrewView(View):
        def __init__(self):
            super().__init__(timeout=180)
            self.current_page = 0
            self.update_buttons()

        def update_buttons(self):
            self.clear_items()

            if self.current_page > 0:
                back_button = Button(label="Back", style=discord.ButtonStyle.primary)
                back_button.callback = self.back_callback
                self.add_item(back_button)

            if self.current_page < total_pages - 1:
                next_button = Button(label="Next", style=discord.ButtonStyle.primary)
                next_button.callback = self.next_callback
                self.add_item(next_button)

        async def back_callback(self, inter: discord.Interaction):
            self.current_page -= 1
            self.update_buttons()
            await inter.response.edit_message(
                embed=create_embed(self.current_page),
                view=self
            )

        async def next_callback(self, inter: discord.Interaction):
            self.current_page += 1
            self.update_buttons()
            await inter.response.edit_message(
                embed=create_embed(self.current_page),
                view=self
            )

        async def interaction_check(self, inter: discord.Interaction) -> bool:
            return inter.user == interaction.user

    view = CrewView()
    await interaction.response.send_message(embed=embed, view=view)
    view.message = await interaction.original_response()

# ======================== ROLE UPDATE ==================

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):

    role = after.guild.get_role(GUILD_MEMBER_ROLE_ID)
    channel = after.guild.get_channel(WELCOME_CHANNEL_ID)

    if not role or not channel:
        return

    async def send_gif_embed(title, description, gif_url, color):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(gif_url) as resp:
                    if resp.status != 200:
                        await channel.send(description)
                        return
                    data = await resp.read()

            embed = discord.Embed(title=title, description=description, color=color)
            embed.set_image(url="attachment://gif.gif")
            await channel.send(embed=embed,
                               file=discord.File(io.BytesIO(data), filename="gif.gif"))
        except:
            await channel.send(description)

    # ROLE ADDED
    if role not in before.roles and role in after.roles:
        data = load_usernames()
        if str(after.id) not in data:
            data[str(after.id)] = "Not set"
            save_usernames(data)
            push_to_github(f"Add {after.name} to usernames.json")

        await send_gif_embed(
            "🎉 Welcome to Bananite Guild!",
            f"Hope you enjoy your time, {after.mention}!",
            WELCOME_IMAGE_URL,
            discord.Color.green()
        )

    # ROLE REMOVED
    if role in before.roles and role not in after.roles:
        data = load_usernames()
        if str(after.id) in data:
            del data[str(after.id)]
            save_usernames(data)
            push_to_github(f"Remove {after.name} from usernames.json")

        await send_gif_embed(
            f"{after.display_name} has left the Guild Crew.",
            "You will not be missed!",
            GOODBYE_IMAGE_URL,
            discord.Color.red()
        )

# ----------------------- STATUS ROTATION -----------------------

statuses = [
    discord.Game(name="Join Bananite Guild"),
    discord.Game(name="discord.gg/bananite")
]

@tasks.loop(seconds=30)
async def rotate_status():
    for status in statuses:
        await bot.change_presence(status=discord.Status.dnd, activity=status)
        await asyncio.sleep(30)

# ----------------------- READY -----------------------

@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    await bot.tree.sync(guild=guild)
    rotate_status.start()
    print(f"Logged in as {bot.user}")

# ----------------------- RUN -----------------------

bot.run(TOKEN)
