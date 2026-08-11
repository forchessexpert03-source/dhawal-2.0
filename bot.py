import os
import discord
from dotenv import load_dotenv
from supabase import create_client
from discord.ext import commands, tasks
from flask import Flask
import threading
import datetime
import json
import pytz
import asyncio
import time
import re
from discord import app_commands
load_dotenv()

TOKEN = os.getenv("TOKEN")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)
# ==============================================================================
# 1. CORE CONFIGURATION & INTENTS SECURITY
# ==============================================================================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = True

# Prefix changed from "!" to "?" — all commands are now used like ?warn, ?mute, ?bump etc.
bot = commands.Bot(command_prefix="?", intents=intents, help_command=None)

# Dictionary maps display labels to target role search strings
COLOR_ROLES_1 = {
    "Crimson": "Crimson", "Hot pink": "Hot pink", "Magenta": "Magenta",
    "Yellow": "Yellow", "Chocolate": "Chocolate", "Aqua": "Aqua",
    "Spring green": "Spring green", "Silver": "Silver", "Red": "Red",
    "Blue": "Blue", "burgundy": "burgundy", "off white": "off white",
    "Laal Mirch": "Laal Mirch", "regular": "regular", "bubblegum": "bubblegum",
    "black": "black", "CB yellow": "CB yellow", "Volcanic Orange": "Volcanic Orange",
    "Nado Grey": "Nado Grey", "Mettalic Blue": "Mettalic Blue"
}

COLOR_ROLES_2 = {
    "Mettalic Bright...": "Mettalic Bright", "Metallic Bronze": "Metallic Bronze",
    "Metallic Choco ...": "Metallic Choco", "Metallic Beach ...": "Metallic Beach",
    "Military Green": "Military Green", "Metallic Vermil...": "Metallic Vermil",
    "Matte Lime Gree.": "Matte Lime Gree", "Minty Green": "Minty Green",
    "Sandy Beige": "Sandy Beige", "Sugar Pink": "Sugar Pink",
    "Deep Mauve": "Deep Mauve", "paperteeth": "paperteeth"
}

ALL_COLOR_NAMES = [name.lower().strip(".") for name in list(COLOR_ROLES_1.values()) + list(COLOR_ROLES_2.values())]

# Moderation role tiers
GREETER_ROLE_NAME = "Greeter"

JUNIOR_ADMIN_ROLE_NAME = "Junior Admin"
MODERATOR_ROLE_NAME = "Moderator"
SUPPORT_ROLE_NAME = "Support Staff"
ADMIN_ROLE_NAME = "Admins"
OWNER_ROLE_NAME = "Owners"
BOOSTER_ROLE_NAME = "Server Booster"
BUMPERS_ROLE_NAME = "Bumpers"
BUMP_FILE = "bump_data.json"

DISBOARD_BOT_ID = 302050872383242240
BUMP_COOLDOWN_SECONDS = 2 * 60 * 60  # 2 hours

# ==============================================================================
# 2. HELPER FUNCTIONS & PERMISSION CHECKS
# ==============================================================================
def has_full_access():
    async def predicate(ctx):

        if ctx.author.guild_permissions.administrator:
            return True

        allowed = {
                JUNIOR_ADMIN_ROLE_NAME,
                SUPPORT_ROLE_NAME,
                ADMIN_ROLE_NAME,
                OWNER_ROLE_NAME
}

        roles = {role.name for role in ctx.author.roles}

        if allowed & roles:
            return True

        await ctx.send("❌ You don't have permission to use this command.",delete_after=10)
        return False

    return commands.check(predicate)


def has_mod_access():
    async def predicate(ctx):

        if ctx.author.guild_permissions.administrator:
            return True

        allowed = {
                MODERATOR_ROLE_NAME,
                SUPPORT_ROLE_NAME,
                ADMIN_ROLE_NAME,
                OWNER_ROLE_NAME,
                JUNIOR_ADMIN_ROLE_NAME
}

        roles = {role.name for role in ctx.author.roles}

        if allowed & roles:
            return True

        await ctx.send("❌ You don't have permission to use this command.",delete_after=10)
        return False

    return commands.check(predicate)

def has_avatar_access():
    async def predicate(ctx):

        if ctx.author.guild_permissions.administrator:
            return True

        allowed = {
            BOOSTER_ROLE_NAME,
            JUNIOR_ADMIN_ROLE_NAME,
            MODERATOR_ROLE_NAME,
            SUPPORT_ROLE_NAME,
            ADMIN_ROLE_NAME,
            OWNER_ROLE_NAME
        }

        roles = {role.name for role in ctx.author.roles}

        if allowed & roles:
            return True

        await ctx.send("❌ You don't have permission to use this command.",delete_after=10)
        return False
    return commands.check(predicate)

def has_junior_admin_access():
    async def predicate(ctx):

        if ctx.author.guild_permissions.administrator:
            return True

        allowed = {
            JUNIOR_ADMIN_ROLE_NAME,
            SUPPORT_ROLE_NAME,
            ADMIN_ROLE_NAME,
            OWNER_ROLE_NAME
        }

        roles = {role.name for role in ctx.author.roles}

        if allowed & roles:
            return True

        await ctx.send("❌ You don't have permission to use this command.",delete_after=10)
        return False

    return commands.check(predicate)

SNIPE_FILE = "edit_logs.json"
SNIPE_HISTORY_FILE = "snipe.json"
WARN_FILE = "warns.json"
AFK_FILE = "afk.json"


def get_ist_time():
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.datetime.now(ist)

def load_json_data(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_json_data(data, filename):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Database write error: {e}")
def get_afk_from_db(guild_id, user_id):
    response = (
        supabase
        .table("afk_data")
        .select("*")
        .eq("guild_id", str(guild_id))
        .eq("user_id", str(user_id))
        .execute()
    )

    if response.data:
        return response.data[0]

    return None


def set_afk_in_db(guild_id, user_id, reason, afk_time, original_name):
    supabase.table("afk_data").upsert({
        "guild_id": str(guild_id),
        "user_id": str(user_id),
        "reason": reason,
        "afk_time": float(afk_time),
        "original_name": original_name
    }).execute()


def remove_afk_from_db(guild_id, user_id):
    supabase.table("afk_data").delete().eq(
        "guild_id", str(guild_id)
    ).eq(
        "user_id", str(user_id)
    ).execute()
# Upgraded Deep Snipe Storage Structure
snipe_data = load_json_data(
    SNIPE_HISTORY_FILE
)# Dynamic multi-level tracking channel_id -> list of deleted msgs
MAX_SNIPE_DEPTH = 100  # Store history trail up to 100 deleted messages deep per channel

def get_flexible_channel(guild, keywords):
    if isinstance(keywords, str):
        keywords = [keywords]
    for channel in guild.text_channels:
        if any(kw in channel.name.lower() for kw in keywords):
            return channel
    return None

def get_bump_channel(guild):
    """Finds whichever text channel has 'bump' anywhere in its name."""
    return get_flexible_channel(guild, "bump")

def schedule_bump_reminder(guild: discord.Guild, channel: discord.TextChannel):
    bump_db = load_json_data(BUMP_FILE)
    bump_db[str(guild.id)] = {
        "channel_id": channel.id,
        "remind_at": time.time() + BUMP_COOLDOWN_SECONDS
    }
    save_json_data(bump_db, BUMP_FILE)

async def send_bot_log(guild, embed):

    channel = get_flexible_channel(
        guild,
        ["bot-logs"]
    )

    if channel:
        await channel.send(embed=embed)

# ==============================================================================
# 3. INTERACTIVE UI ELEMENTS (CASE INSENSITIVE SMART COLOR SEARCH)
# ==============================================================================
class ColorSelectMenu(discord.ui.Select):
    def __init__(self, placeholder, options_dict, custom_id):
        options = [
            discord.SelectOption(label=label, value=role_name, emoji="🎨")
            for label, role_name in options_dict.items()
        ]
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options, custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        member = interaction.user

        # Super clean string normalization
        selected_search = self.values[0].lower().strip(". ").replace("mettalic", "metallic")

        # Clean removal routine matching case-insensitive variants
        roles_to_remove = [
            role for role in member.roles
            if role.name.lower().strip(". ").replace("mettalic", "metallic") in ALL_COLOR_NAMES
            and role.name.lower().strip(". ").replace("mettalic", "metallic") != selected_search
        ]
        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove)
            except discord.Forbidden:
                await interaction.followup.send("❌ Discord Hierarchy limits: Put Bot's role above all color roles!", ephemeral=True)
                return

        # Ultra flexible matching: checks startswith, substring, and reverse inclusion
        target_role = discord.utils.find(
            lambda r: (
                selected_search in r.name.lower() or
                r.name.lower().strip(". ").replace("mettalic", "metallic").startswith(selected_search) or
                selected_search.startswith(r.name.lower().strip(". "))
            ),
            guild.roles
        )

        if target_role:
            try:
                if target_role in member.roles:
                    await member.remove_roles(target_role)
                    await interaction.followup.send(f"🎨 Removed your **{target_role.name}** color configuration.", ephemeral=True)
                else:
                    await member.add_roles(target_role)
                    await interaction.followup.send(f"🎨 Success! Activated custom color shade **{target_role.name}**.", ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send("❌ Role addition failed. Verify internal permission flags.", ephemeral=True)
        else:
            await interaction.followup.send(
                f"❌ **Error:** Visual role for '{self.values[0]}' not found.\n"
                f"💡 *Tip:* Make sure the role name on your Discord Server matches or contains the words **'{self.values[0].strip('.')}'**!",
                ephemeral=True
            )

class ColorView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ColorSelectMenu("Pick Color (Part 1: 1-20)...", COLOR_ROLES_1, "general:color_select_1"))
        self.add_item(ColorSelectMenu("Pick Color (Part 2: 21-32)...", COLOR_ROLES_2, "general:color_select_2"))

# ==============================================================================
# SELF ROLE SYSTEM
# ==============================================================================

SELF_ROLE_CHANNEL_KEYWORDS = [
    "self-roles",
    "self roles",
    "selfroles"
]

GENDER_ROLES = {
    "👨 Male": "Male",
    "👩 Female": "Female"
}

AGE_ROLES = {
    "🔹 13–17": "13-17",
    "🔹 18–24": "18-24",
    "🔹 25–30": "25-30",
    "🔹 30+": "30+"
}

GAME_ROLES = {
    "🎲 Cambio": "Cambio",
    "🏦 Monopoly": "Monopoly",
    "🎯 Valorant": "Valorant",
    "✏️ Scribbl": "Scribbl",
    "🎵 Music Guesser": "Music Guesser",
    "🧱 Roblox": "Roblox",
    "🕵️ CodeNames": "CodeNames",
    "♟️ Chess": "Chess"
}

NSFW_ROLE = "Gooners"


def find_role(guild, role_name):
    return discord.utils.find(
        lambda role: role.name.lower() == role_name.lower(),
        guild.roles
    )


class SelfRoleSelect(discord.ui.Select):

    def __init__(
        self,
        placeholder,
        roles_dict,
        custom_id,
        exclusive=False
    ):

        options = [
            discord.SelectOption(
                label=label,
                value=role_name
            )
            for label, role_name in roles_dict.items()
        ]

        super().__init__(
            placeholder=placeholder,
            min_values=0,
            max_values=1 if exclusive else len(options),
            options=options,
            custom_id=custom_id
        )

        self.roles_dict = roles_dict
        self.exclusive = exclusive

    async def callback(self, interaction: discord.Interaction):

        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        member = interaction.user

        selected_roles = set(self.values)

        # ----------------------------------------------------------
        # EXCLUSIVE ROLE GROUPS
        # ----------------------------------------------------------

        if self.exclusive:

            selected_role_name = self.values[0] if self.values else None

            for role_name in self.roles_dict.values():

                role = find_role(guild, role_name)

                if role and role in member.roles:

                    if role_name != selected_role_name:

                        try:
                            await member.remove_roles(role)
                        except discord.Forbidden:
                            await interaction.followup.send(
                                "❌ I cannot manage one of these roles. "
                                "Please move Dhawal's role above the self-roles.",
                                ephemeral=True
                            )
                            return

            if selected_role_name:

                target_role = find_role(
                    guild,
                    selected_role_name
                )

                if not target_role:

                    await interaction.followup.send(
                        f"❌ Role `{selected_role_name}` was not found.",
                        ephemeral=True
                    )
                    return

                if target_role not in member.roles:

                    try:
                        await member.add_roles(target_role)
                    except discord.Forbidden:

                        await interaction.followup.send(
                            "❌ I cannot manage this role. "
                            "Move Dhawal's role above the self-roles.",
                            ephemeral=True
                        )
                        return

                await interaction.followup.send(
                    f"✅ Your role is now **{target_role.name}**.",
                    ephemeral=True
                )

            return

        # ----------------------------------------------------------
        # MULTI-SELECT GAME ROLES
        # ----------------------------------------------------------

        added = []
        removed = []

        for role_name in self.roles_dict.values():

            role = find_role(guild, role_name)

            if not role:
                continue

            if role_name in selected_roles:

                if role not in member.roles:

                    try:
                        await member.add_roles(role)
                        added.append(role.name)
                    except discord.Forbidden:
                        pass

            else:

                if role in member.roles:

                    try:
                        await member.remove_roles(role)
                        removed.append(role.name)
                    except discord.Forbidden:
                        pass

        response = []

        if added:
            response.append(
                "✅ Added: " +
                ", ".join(f"**{role}**" for role in added)
            )

        if removed:
            response.append(
                "🗑️ Removed: " +
                ", ".join(f"**{role}**" for role in removed)
            )

        if not response:
            response.append(
                "ℹ️ No changes were made."
            )

        await interaction.followup.send(
            "\n".join(response),
            ephemeral=True
        )


class NSFWRoleButton(discord.ui.Button):

    def __init__(self):

        super().__init__(
            label="🔞 Get Gooners Role",
            style=discord.ButtonStyle.danger,
            custom_id="selfrole:nsfw"
        )

    async def callback(self, interaction: discord.Interaction):

        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        member = interaction.user

        role = find_role(
            guild,
            NSFW_ROLE
        )

        if not role:

            await interaction.followup.send(
                "❌ The `Gooners` role was not found.",
                ephemeral=True
            )
            return

        try:

            if role in member.roles:

                await member.remove_roles(role)

                await interaction.followup.send(
                    "🔞 Gooners role removed.",
                    ephemeral=True
                )

            else:

                await member.add_roles(role)

                await interaction.followup.send(
                    "🔞 Gooners role added.",
                    ephemeral=True
                )

        except discord.Forbidden:

            await interaction.followup.send(
                "❌ I cannot manage the Gooners role. "
                "Move Dhawal's role above it.",
                ephemeral=True
            )


class SelfRoleView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

        # Gender - ONE ONLY
        self.add_item(
            SelfRoleSelect(
                "👤 Select your gender",
                GENDER_ROLES,
                "selfrole:gender",
                exclusive=True
            )
        )

        # Age - ONE ONLY
        self.add_item(
            SelfRoleSelect(
                "🎂 Select your age group",
                AGE_ROLES,
                "selfrole:age",
                exclusive=True
            )
        )

        # Games - MULTIPLE
        self.add_item(
            SelfRoleSelect(
                "🎮 Select your games",
                GAME_ROLES,
                "selfrole:games",
                exclusive=False
            )
        )

        # NSFW
        self.add_item(
            NSFWRoleButton()
        )

@bot.command(
    name="self-roles",
    aliases=["selfroles", "selfrole"],
    help="Post the self-role selection panel."
)
@has_full_access()
async def self_roles(ctx: commands.Context):

    embed = discord.Embed(
        title="🎭 Self Roles",
        description=(
            "**Choose your roles below!**\n\n"
            "👤 **Gender** — Choose **one**\n"
            "🎂 **Age** — Choose **one**\n"
            "🎮 **Games** — Choose as many as you want\n\n"
            "────────────────────────\n\n"
            "🔞 **NSFW Access**\n"
            "Want access to NSFW content? "
            "Get the **Gooners** role below."
        ),
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="👤 Gender",
        value="Choose one option.",
        inline=False
    )

    embed.add_field(
        name="🎂 Age Group",
        value="Choose one age group.",
        inline=False
    )

    embed.add_field(
        name="🎮 Games",
        value=(
            "Select every game you play.\n"
            "You can choose multiple."
        ),
        inline=False
    )

    embed.add_field(
        name="🔞 NSFW",
        value=(
            "For NSFW content, click "
            "**Get Gooners Role**."
        ),
        inline=False
    )

    embed.set_footer(
        text="You can change your selections anytime."
    )

    await ctx.send(
        embed=embed,
        view=SelfRoleView()
    )

# ==============================================================================
# 5. EVENT DECORATORS & INTERCEPTORS (WELCOME, AFK, BUMP DETECTION)
# ==============================================================================
@bot.event
async def on_ready():
    print(f'🤖 {bot.user.name} Master Routing Cluster Bootstrapped successfully!')
    await bot.tree.sync()
    print("✅ Slash commands synced.")
    bot.add_view(ColorView())
    bot.add_view(SelfRoleView())
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Abhi9av 👑"))
    if not bump_reminder_loop.is_running():
        bump_reminder_loop.start()
    print("Prefix commands ready. Using '?' as the command prefix.")

@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild

    general_channel = get_flexible_channel(
        guild,
        ["general", "general-chat"]
    )

    welcome_channel = get_flexible_channel(
        guild,
        ["welcome"]
    )

    welcome_logs_channel = get_flexible_channel(
        guild,
        ["welcome-logs"]
    )

    join_leave_channel = get_flexible_channel(
        guild,
        ["join-leave", "join-leave-logs"]
    )

    total_members = len(guild.members)

    if total_members % 10 == 1 and total_members % 100 != 11:
        suffix = "st"
    elif total_members % 10 == 2 and total_members % 100 != 12:
        suffix = "nd"
    elif total_members % 10 == 3 and total_members % 100 != 13:
        suffix = "rd"
    else:
        suffix = "th"

    aquasmile_emoji = discord.utils.get(
        guild.emojis,
        name="Aquasmile"
    )

    emoji_str = str(aquasmile_emoji) if aquasmile_emoji else "😊"

    rules_channel = get_flexible_channel(guild, "rules")
    rules_mention = rules_channel.mention if rules_channel else "#rules"

    greeter_role = discord.utils.get(
        guild.roles,
        name=GREETER_ROLE_NAME
    )

    greeter_mention = (
        greeter_role.mention
        if greeter_role
        else "@Greeter"
    )

    outer_content_text = (
        f"Welcome to Kuch Nahi Family 🤗 "
        f"{member.mention} {greeter_mention}"
    )

    clean_welcome_text = (
        f"Drop a hello {emoji_str}\n"
        f"Check out {rules_mention}\n"
        f"Have fun!\n\n"
        f"**You are our {total_members}{suffix} member!**"
    )

    embed = discord.Embed(
        description=clean_welcome_text,
        color=discord.Color.from_rgb(255, 182, 193)
    )

    embed.set_author(
        name=member.name,
        icon_url=member.display_avatar.url
    )

    # General chat
    if general_channel:
        if os.path.exists("welcome.webp"):
            file = discord.File(
                "welcome.webp",
                filename="welcome.webp"
            )

            embed.set_thumbnail(
                url="attachment://welcome.webp"
            )

            await general_channel.send(
                content=outer_content_text,
                file=file,
                embed=embed
            )
        else:
            await general_channel.send(
                content=outer_content_text,
                embed=embed
            )

    # Welcome channel
    if welcome_channel:
        await welcome_channel.send(
            f"🎉 {member.mention} has arrived!"
        )

    # Welcome logs
    if welcome_logs_channel:
        log_embed = discord.Embed(
            title="✅ Member Joined",
            color=discord.Color.green()
        )

        log_embed.add_field(
            name="User",
            value=f"{member} ({member.id})",
            inline=False
        )

        await welcome_logs_channel.send(
            embed=log_embed
        )

    # Join/leave logs
    if join_leave_channel:
        await join_leave_channel.send(
            f"🟢 {member} joined the server."
        )

@bot.event
async def on_member_remove(member):

    channel = get_flexible_channel(
        member.guild,
        ["join-leave", "join-leave-logs"]
    )

    if not channel:
        return

    embed = discord.Embed(
        title="❌ Member Left",
        color=discord.Color.red()
    )

    embed.add_field(
        name="User",
        value=f"{member} ({member.id})",
        inline=False
    )

    embed.add_field(
        name="Account created",
        value=member.created_at.strftime(
            "%d-%m-%Y %I:%M %p"
        ),
        inline=False
    )

    embed.set_thumbnail(
        url=member.display_avatar.url
    )

    await channel.send(embed=embed)
    


@bot.event
async def on_message(message):

    # Ignore messages sent by bots
    if message.author.bot:
        # Detect Disboard's successful bump confirmation and auto-schedule the 2 hour reminder
        if message.guild and message.author.id == DISBOARD_BOT_ID and message.embeds:
            embed_desc = (message.embeds[0].description or "").lower()
            if "bump done" in embed_desc or "check it out on disboard" in embed_desc:
                bump_channel = get_bump_channel(message.guild) or message.channel
                schedule_bump_reminder(message.guild, bump_channel)
                await bump_channel.send("✅ Bump registered! I'll ping **Bumpers** in 2 hours for the next one. 🔔")
        return

    # Ignore DMs
    if not message.guild:
        return

    author_id = str(message.author.id)
    guild_id = str(message.guild.id)

    # ---------------------------------------------------------
    # REMOVE AFK WHEN THE AFK USER SENDS A MESSAGE
    # ---------------------------------------------------------

    author_afk = get_afk_from_db(guild_id, author_id)

    if author_afk:
        original_name = author_afk.get(
            "original_name",
            message.author.display_name
        )

        remove_afk_from_db(guild_id, author_id)

        try:
            await message.author.edit(nick=original_name)
        except discord.Forbidden:
            pass

        await message.channel.send(
            f"wb {message.author.mention}, maine aapka AFK status hata diya hai! 👋",
            delete_after=5
        )

    # ---------------------------------------------------------
    # CHECK IF SOMEONE MENTIONED AN AFK USER
    # ---------------------------------------------------------

    if message.mentions:
        for mentioned_user in message.mentions:
            m_id = str(mentioned_user.id)
            mentioned_afk = get_afk_from_db(guild_id, m_id)

            if mentioned_afk:
                reason = mentioned_afk.get("reason", "AFK")
                afk_time = float(mentioned_afk.get("afk_time", time.time()))

                elapsed = max(0, int(time.time() - afk_time))

                if elapsed < 60:
                    duration_str = f"{elapsed}s ago"
                elif elapsed < 3600:
                    duration_str = f"{elapsed // 60}m ago"
                else:
                    duration_str = f"{elapsed // 3600}h ago"

                await message.channel.send(
                    f"💤 {mentioned_user.name} abhi AFK hain: "
                    f"**{reason}** ({duration_str})",
                    reference=message
                )

    await bot.process_commands(message)

@bot.event
async def on_message_delete(message):
    if message.author.bot or not message.guild: return
    channel_id = str(message.channel.id)
    guild_id = str(message.guild.id)
    history_db = load_json_data(SNIPE_FILE)
    msg_id = str(message.id)
    was_edited = msg_id in history_db and history_db[msg_id].get("guild_id") == guild_id
        # =========================================================
    # MESSAGE LOGS - DELETED MESSAGE
    # =========================================================

    message_logs_channel = get_flexible_channel(
        message.guild,
        ["message-logs", "message logs"]
    )

    if message_logs_channel:

        log_embed = discord.Embed(
            title="🗑️ Message Deleted",
            color=discord.Color.red()
        )

        log_embed.add_field(
            name="👤 Author",
            value=f"{message.author.mention} (`{message.author.id}`)",
            inline=False
        )

        log_embed.add_field(
            name="📍 Channel",
            value=message.channel.mention,
            inline=False
        )

        log_embed.add_field(
            name="💬 Content",
            value=message.content[:1024] if message.content else "No text content",
            inline=False
        )

        if message.attachments:
            attachments = "\n".join(
                attachment.url for attachment in message.attachments
            )

            log_embed.add_field(
                name="📎 Attachments",
                value=attachments[:1024],
                inline=False
            )

        log_embed.set_thumbnail(
            url=message.author.display_avatar.url
        )

        log_embed.set_footer(
            text=get_ist_time().strftime("%d-%m-%Y %I:%M:%S %p")
        )

        await message_logs_channel.send(
            embed=log_embed
        )
    edit_note = ""
    if was_edited:
        edit_note = f"\n*(⚠️ Note: Message was updated prior to deletion. State captured: \"{history_db[msg_id]['before']}\")*"

    if channel_id not in snipe_data:
        snipe_data[channel_id] = []

    payload = {
        "content": message.content if message.content else "[Empty Layer or File Stream Embedded]",
        "author": message.author.name,
        "author_id": str(message.author.id),
        "avatar": message.author.display_avatar.url,
        "timestamp": get_ist_time().strftime("%I:%M:%S %p"),
        "extra_info": edit_note
    }

    # Insert at index 0 so position 1 is always the latest deleted message
    snipe_data[channel_id].insert(0, payload)

    save_json_data(
    snipe_data,
    SNIPE_HISTORY_FILE
)

    # Restrict trail size up to 20 messages deep per channel
    if len(snipe_data[channel_id]) > MAX_SNIPE_DEPTH:
        snipe_data[channel_id].pop()

        save_json_data(
            snipe_data,
            SNIPE_HISTORY_FILE
        )
    

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content or not before.guild: return
    guild_id = str(before.guild.id)
    history_db = load_json_data(SNIPE_FILE)
    history_db[str(before.id)] = {
        "guild_id": guild_id,
        "author": before.author.name,
        "author_id": str(before.author.id),
        "before": before.content,
        "after": after.content,
        "timestamp": get_ist_time().strftime("%Y-%m-%d %I:%M %p")
    }
    if len(history_db) > 100:
        history_db.pop(list(history_db.keys())[0])
    save_json_data(history_db, SNIPE_FILE)
        # =========================================================
    # MESSAGE LOGS - EDITED MESSAGE
    # =========================================================

    message_logs_channel = get_flexible_channel(
        before.guild,
        ["message-logs", "message logs"]
    )

    if message_logs_channel:

        log_embed = discord.Embed(
            title="✏️ Message Edited",
            color=discord.Color.orange()
        )

        log_embed.add_field(
            name="👤 Author",
            value=f"{before.author.mention} (`{before.author.id}`)",
            inline=False
        )

        log_embed.add_field(
            name="📍 Channel",
            value=before.channel.mention,
            inline=False
        )

        log_embed.add_field(
            name="📝 Before",
            value=before.content[:1024] if before.content else "No text content",
            inline=False
        )

        log_embed.add_field(
            name="✏️ After",
            value=after.content[:1024] if after.content else "No text content",
            inline=False
        )

        log_embed.set_thumbnail(
            url=before.author.display_avatar.url
        )

        log_embed.set_footer(
            text=get_ist_time().strftime("%d-%m-%Y %I:%M:%S %p")
        )

        await message_logs_channel.send(
            embed=log_embed
        )

@bot.event
async def on_command_error(ctx, error):

    if isinstance(error, commands.CheckFailure):
        return

    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, commands.MissingRequiredArgument):

        if ctx.command.name == "mute":
            await ctx.send(
                "**Mute Usage:**\n\n"
                "`?mute @member 10m`\n"
                "`?mute @member 30m`\n"
                "`?mute @member 1h`\n"
                "`?mute @member 2h`\n"
                "`?mute @member 1d`\n"
                "`?mute @member 7d`\n"
                "`?mute @member 1h Spamming`"
            )
            return

        await ctx.send(
            f"❌ Missing argument: `{error.param.name}`.\nUse `?help {ctx.command}`"
        )
        return

    if isinstance(error, commands.MemberNotFound):
        await ctx.send(
            "❌ Could not find that member. Try mentioning them directly."
        )
        return

    if isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Bad argument: `{error}`")
        return

    print(f"Unhandled command error: {error}")
    await ctx.send(f"❌ Execution error: `{error}`")

# ==============================================================================
# 6. BUMP REMINDER BACKGROUND LOOP
# ==============================================================================
@tasks.loop(minutes=1)
async def bump_reminder_loop():
    bump_db = load_json_data(BUMP_FILE)
    if not bump_db:
        return
    now = time.time()
    changed = False
    for guild_id, entry in list(bump_db.items()):
        if entry.get("remind_at", float("inf")) <= now:
            guild = bot.get_guild(int(guild_id))
            if guild:
                channel = guild.get_channel(entry.get("channel_id"))
                bumpers_role = discord.utils.get(guild.roles, name=BUMPERS_ROLE_NAME)
                if channel:
                    mention = bumpers_role.mention if bumpers_role else "@Bumpers"
                    try:
                        await channel.send(f"⏰ {mention} It's time to bump the server again! Use `/bump` here to keep us on top of Disboard. 🚀")
                    except discord.Forbidden:
                        pass
            bump_db.pop(guild_id)
            changed = True
    if changed:
        save_json_data(bump_db, BUMP_FILE)

@bump_reminder_loop.before_loop
async def before_bump_loop():
    await bot.wait_until_ready()

# ==============================================================================
# 7. GENERAL UTILITIES, UTILS, & EXCLUSIVE AVATAR SYSTEMS
# ==============================================================================

@bot.command(name="afk", help="Set your profile status to AFK. Usage: ?afk <reason>")
async def afk(ctx: commands.Context, *, reason: str = "Working / Afk"):
    user_id = str(ctx.author.id)
    guild_id = str(ctx.guild.id)

    # Block re-applying AFK if user is already AFK
    existing_afk = get_afk_from_db(guild_id, user_id)

    if existing_afk:
        existing_reason = existing_afk.get("reason", "AFK")
        await ctx.send(
            f"❌ {ctx.author.mention}, aap already AFK hain: "
            f"**{existing_reason}**. Kuch bhi message bhejo AFK hatane ke liye!"
        )
        return

    current_display_name = ctx.author.display_name
    afk_time = time.time()

    set_afk_in_db(
        guild_id=guild_id,
        user_id=user_id,
        reason=reason,
        afk_time=afk_time,
        original_name=current_display_name
    )

    try:
        new_nick = f"[AFK] {current_display_name}"[:32]
        await ctx.author.edit(nick=new_nick)
    except discord.Forbidden:
        pass

    await ctx.send(
        f"💤 {ctx.author.mention}, aap ab AFK hain: **{reason}**"
    )
@bot.command(
    name="afkclear",
    aliases=["afk-clear"],
    help="Clear someone's AFK status.\nUsage: ?afkclear @member"
)
@has_full_access()
async def afk_clear(ctx: commands.Context, member: discord.Member):

    guild_id = str(ctx.guild.id)
    user_id = str(member.id)

    afk_data = get_afk_from_db(guild_id, user_id)

    if not afk_data:
        await ctx.send(f"✅ {member.mention} is not AFK.")
        return

    original_name = afk_data.get(
        "original_name",
        member.display_name
    )

    remove_afk_from_db(guild_id, user_id)

    try:
        await member.edit(nick=original_name)
    except discord.Forbidden:
        pass

    await ctx.send(
        f"✅ Cleared AFK status for {member.mention}."
    )

@bot.command(
    name="avatar",
    aliases=["av"],
    help="Usage:\n?av\n?av @member"
)
@has_avatar_access()
async def avatar(ctx: commands.Context, member: discord.Member = None):

    if member is None:
        member = ctx.author

    embed = discord.Embed(
        title=f"{member.display_name}'s Avatar",
        color=member.color if member.color.value != 0 else discord.Color.blurple()
    )

    embed.set_image(url=member.display_avatar.url)

    embed.set_footer(
        text=f"Requested by {ctx.author.display_name}"
    )

    await ctx.send(embed=embed)
    
@bot.command(name="color-list", help="Show the custom colors identity preview sheet.")
@has_full_access()
async def color_list(ctx: commands.Context):
    target_file = "color_list.webp"
    if not os.path.exists(target_file):
        await ctx.send("❌ Media Reference Failure: Local asset file designated `color_list.webp` not found.")
        return
    file = discord.File(target_file, filename="color_list.webp")
    embed = discord.Embed(
        title="🎨 Kuch Nahi - Colors Ledger Selection Guide",
        description="Review the reference identity mapping chart below to preview visual configuration values.",
        color=discord.Color.from_rgb(47, 49, 54)
    )
    embed.set_image(url="attachment://color_list.webp")
    await ctx.send(file=file, embed=embed)

@bot.command(name="setup-colors", help="Post the custom color picker panel.")
@has_full_access()
async def setup_colors(ctx: commands.Context):
    embed = discord.Embed(
        title="🌈 Custom Color Picker Panel",
        description="Select your desired identity color role setup using the multi-dropdown matrix arrays below.\n\nChoose any tone to map it instantly!",
        color=discord.Color.blurple()
    )
    await ctx.send(embed=embed, view=ColorView())

@bot.command(name="snipe", help="Retrieve recent deleted messages. Usage: ?snipe [index]")
@has_mod_access()
async def snipe(ctx: commands.Context, index: int = 1):
    channel_id = str(ctx.channel.id)

    if channel_id not in snipe_data or not snipe_data[channel_id]:
        await ctx.send("❌ There are no recent text string deletions found in this tracking loop scope.")
        return

    total_logs = len(snipe_data[channel_id])

    if index < 1 or index > total_logs:
        await ctx.send(
            f"❌ **Index Out of Bounds!** Abhi is channel mein sirf pichle `{total_logs}` deleted messages ka record hai.\n"
            f"Try checking a value between `1` and `{total_logs}`."
        )
        return

    data = snipe_data[channel_id][index - 1]

    embed = discord.Embed(description=f"{data['content']}{data['extra_info']}", color=discord.Color.red())
    embed.set_author(name=f"Deleted by: {data['author']}", icon_url=data['avatar'])
    embed.set_footer(text=f"Position: {index}/{total_logs} Last Deleted | Time: {data['timestamp']} (IST Zone Forced)")
    await ctx.send(embed=embed)

@bot.command(
    name="history",
    help="Usage: ?history @member [count]"
)
@has_mod_access()
async def history(
    ctx,
    member: discord.Member,
    count: int = 10
):

    channel_id = str(ctx.channel.id)

    if channel_id not in snipe_data:
        await ctx.send("❌ No deleted messages found.")
        return

    if count < 1:
        count = 1

    if count > 100:
        count = 100

    logs = []

    for msg in snipe_data[channel_id]:

        if msg.get("author_id") == str(member.id):

            logs.append(msg)

    if not logs:

        await ctx.send(
            f"❌ No deleted messages found for {member.mention}."
        )

        return

    logs = logs[:count]

    embed = discord.Embed(
        title=f"🗑️ Deleted Message History • {member}",
        color=discord.Color.red()
    )

    for index, msg in enumerate(logs, start=1):

        content = msg["content"]

        if len(content) > 1000:
            content = content[:1000] + "..."

        embed.add_field(
            name=f"{index}. {msg['timestamp']}",
            value=f"```{content}```",
            inline=False
        )

    embed.set_thumbnail(
        url=member.display_avatar.url
    )

    embed.set_footer(
        text=f"Showing {len(logs)} of {len([m for m in snipe_data[channel_id] if m.get('author_id') == str(member.id)])} stored deleted messages"
    )

    await ctx.send(embed=embed)

@bot.command(name="editlogs", help="Check historical edit logs. Usage: ?editlogs @member")
async def editlogs(ctx: commands.Context, member: discord.Member):
    history_db = load_json_data(SNIPE_FILE)
    guild_id = str(ctx.guild.id)
    target_user_id = str(member.id)

    found_log = None
    for msg_id in reversed(list(history_db.keys())):
        log = history_db[msg_id]
        if log.get("guild_id") == guild_id and log.get("author_id") == target_user_id:
            found_log = log
            break

    if not found_log:
        await ctx.send(f"✅ Zero trace adjustments: No edited frames found for {member.name}.")
        return

    embed = discord.Embed(title=f"📝 Message Edit Log Asset: {member.name}", color=discord.Color.blue())
    embed.add_field(name="⏪ Original Form String", value=f"```\n{found_log['before']}\n```", inline=False)
    embed.add_field(name="⏩ Modified Target State", value=f"```\n{found_log['after']}\n```", inline=False)
    embed.set_footer(text=f"Timestamp: {found_log['timestamp']} (IST Matrix)")
    await ctx.send(embed=embed)

# ==============================================================================
# 9. SERVER BUMP SYSTEM (DISBOARD)
# ==============================================================================
@bot.command(name="bump", help="Bump reminder helper. Points to Disboard's /bump and starts the 2h reminder timer.")
async def bump_cmd(ctx: commands.Context):
    bump_channel = get_bump_channel(ctx.guild) or ctx.channel
    schedule_bump_reminder(ctx.guild, bump_channel)
    await ctx.send(
        f"📢 To actually bump us on Disboard, run Disboard's own `/bump` slash command here in {bump_channel.mention}.\n"
        f"⏰ I've started the 2 hour countdown — I'll ping **@{BUMPERS_ROLE_NAME}** here when it's time to bump again!"
    )

# ==============================================================================
# 8. ROLE MANAGEMENT (STAFF ONLY)
# ==============================================================================
@bot.command(name="role", help='Give/remove a role. Usage: ?role @member +RoleName  OR  ?role @member -RoleName')
@has_mod_access()
async def role_cmd(ctx: commands.Context, member: discord.Member, *, role_action: str):
    role_action = role_action.strip()
    if not role_action or role_action[0] not in ("+", "-"):
        await ctx.send("❌ Format Error: Use `?role @member +RoleName` to add or `?role @member -RoleName` to remove.")
        return

    action = role_action[0]
    role_name = role_action[1:].strip()
    if not role_name:
        await ctx.send("❌ Format Error: You must specify a role name after `+` or `-`.")
        return

    target_role = discord.utils.find(lambda r: r.name.lower() == role_name.lower(), ctx.guild.roles)
    if not target_role:
        await ctx.send(f"❌ Role `{role_name}` not found on this server.")
        return

# ----- Security Check -----

# Bot role must be above the target role
    if target_role >= ctx.guild.me.top_role:
        await ctx.send("❌ I can't manage that role because it is above my highest role.")
        return

# User cannot manage roles equal to or above their own top role
    if target_role >= ctx.author.top_role:
        await ctx.send("❌ You cannot assign or remove a role that is equal to or higher than your highest role.")
        return
    protected_roles = {
    OWNER_ROLE_NAME,
    ADMIN_ROLE_NAME,
    SUPPORT_ROLE_NAME,
    MODERATOR_ROLE_NAME,
    JUNIOR_ADMIN_ROLE_NAME
}

    if target_role.name in protected_roles:
        await ctx.send("❌ This protected staff role cannot be assigned or removed using this command.")
        return
    try:
        if action == "+":
            if target_role in member.roles:
                await ctx.send(f"⚠️ {member.mention} already has **{target_role.name}**.")
                return
            await member.add_roles(target_role)
            await ctx.send(f"✅ Added **{target_role.name}** to {member.mention}.")
        else:
            if target_role not in member.roles:
                await ctx.send(f"⚠️ {member.mention} doesn't have **{target_role.name}**.")
                return
            await member.remove_roles(target_role)
            await ctx.send(f"🗑️ Removed **{target_role.name}** from {member.mention}.")
    except discord.Forbidden:
        await ctx.send("❌ Discord Hierarchy limits: Put Bot's role above the target role!")

# ==============================================================================
# 10. STAFF ONLY ENFORCEMENT & MODERATION MODULES
# ==============================================================================
@bot.command(name="warn", help="Issue a warning. Usage: ?warn @member <reason>")
@has_mod_access()
async def warn(ctx: commands.Context, member: discord.Member, *, reason: str):
    warns_db = load_json_data(WARN_FILE)
    m_id = str(member.id)
    g_id = str(ctx.guild.id)

    if g_id not in warns_db: warns_db[g_id] = {}
    if m_id not in warns_db[g_id]: warns_db[g_id][m_id] = []

    warn_payload = {
        "warn_id": len(warns_db[g_id][m_id]) + 1,
        "moderator": ctx.author.name,
        "reason": reason,
        "timestamp": get_ist_time().strftime("%Y-%m-%d %I:%M %p")
    }
    warns_db[g_id][m_id].append(warn_payload)
    save_json_data(warns_db, WARN_FILE)

    embed = discord.Embed(title="⚠️ Member Warning Registered", color=discord.Color.orange())
    embed.add_field(name="User Info", value=member.mention, inline=True)
    embed.add_field(name="Total Violations", value=str(len(warns_db[g_id][m_id])), inline=True)
    embed.add_field(name="Reason Specification", value=reason, inline=False)
    await ctx.send(embed=embed)
    log_embed = discord.Embed(
    title="⚠️ Warning Issued",
    color=discord.Color.orange()
)

    log_embed.add_field(
    name="Member",
    value=member.mention,
    inline=False
)

    log_embed.add_field(
    name="Moderator",
    value=ctx.author.mention,
    inline=False
)

    log_embed.add_field(
    name="Reason",
    value=reason,
    inline=False
)

    await send_bot_log(ctx.guild, log_embed)

@bot.command(name="warns", help="View warning history. Usage: ?warns @member")
@has_mod_access()
async def views_warns(ctx: commands.Context, member: discord.Member):
    warns_db = load_json_data(WARN_FILE)
    m_id = str(member.id)
    g_id = str(ctx.guild.id)

    if g_id not in warns_db or m_id not in warns_db[g_id] or not warns_db[g_id][m_id]:
        await ctx.send(f"✅ Clean Slate: {member.name} contains zero moderation flags.")
        return

    embed = discord.Embed(title=f"📋 Enforcement Violation Log: {member.name}", color=discord.Color.yellow())
    for item in warns_db[g_id][m_id]:
        embed.add_field(
            name=f"Case ID: #{item['warn_id']} | Date: {item['timestamp']}",
            value=f"**Reason:** {item['reason']}\n**Issued By:** {item['moderator']}",
            inline=False
        )
    await ctx.send(embed=embed)

@bot.command(name="clear-warns", help="Purge a member's warnings. Usage: ?clear-warns @member")
@has_full_access()
async def clear_warns(ctx: commands.Context, member: discord.Member):
    warns_db = load_json_data(WARN_FILE)
    m_id = str(member.id)
    g_id = str(ctx.guild.id)

    if g_id in warns_db and m_id in warns_db[g_id]:
        warns_db[g_id].pop(m_id)
        save_json_data(warns_db, WARN_FILE)
    await ctx.send(f"🗑️ System cleanup: Warnings ledger cleared for {member.mention}.")

@bot.command(
    name="mute",
    help="""
Usage:
?mute @member 10m
?mute @member 1h
?mute @member 1d
?mute @member 30m Spamming
"""
)
@has_mod_access()
async def mute(
    ctx: commands.Context,
    member: discord.Member,
    duration: str,
    *,
    reason: str = "No reason provided."
):

    match = re.fullmatch(r"(\d+)([mhd])", duration.lower())
    if not match:
        await ctx.send("Invalid format")
        return
    amount=int(match.group(1))
    unit=match.group(2)
    if unit=="m":
        delta=datetime.timedelta(minutes=amount)
    elif unit=="h":
        delta=datetime.timedelta(hours=amount)
    else:
        delta=datetime.timedelta(days=amount)
    try:
        await member.timeout(delta, reason=reason)
        embed=discord.Embed(title="🔇 Member Muted", color=discord.Color.red())
        embed.add_field(name="Member", value=member.mention, inline=True)
        embed.add_field(name="Duration", value=duration, inline=True)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        await ctx.send(embed=embed)
        log_embed=discord.Embed(title="🔇 Member Muted", color=discord.Color.red())
        log_embed.add_field(name="Member", value=member.mention, inline=False)
        log_embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
        log_embed.add_field(name="Duration", value=duration, inline=False)
        log_embed.add_field(name="Reason", value=reason, inline=False)
        await send_bot_log(ctx.guild, log_embed)
    except Exception as e:
        await ctx.send(f"❌ {e}")

@bot.command(name="unmute", help="Remove a member's timeout. Usage: ?unmute @member")
@has_mod_access()
async def unmute(ctx: commands.Context, member: discord.Member):
    try:
        await member.timeout(None)
        await ctx.send(f"🔊 Communication routing restored for profile user {member.mention}.")
    except Exception as e:
        await ctx.send(f"❌ Execution failure: `{str(e)}`")

@bot.command(name="kick", help="Kick a member. Usage: ?kick @member <reason>")
@has_junior_admin_access()
async def kick(ctx: commands.Context, member: discord.Member, *, reason: str = "Unspecified"):
    try:
        await member.kick(reason=reason)
        await ctx.send(f"👢 Kicked {member.name} successfully. Reason code: `{reason}`")
    except Exception as e:
        await ctx.send(f"❌ Command denied execution path: `{str(e)}`")

@bot.command(name="ban", help="Ban a member. Usage: ?ban @member <reason>")
@has_junior_admin_access()
async def ban(ctx: commands.Context, member: discord.Member, *, reason: str = "Unspecified"):
    try:
        await member.ban(reason=reason)
        await ctx.send(f"🔨 Banned user identity hash {member.name} cleanly. Reason: `{reason}`")
    except Exception as e:
        await ctx.send(f"❌ Execution pipeline blocked: `{str(e)}`")

@bot.command(
    name="unban",
    help="Unban a user using their User ID.\nUsage: ?unban <user_id>"
)
@has_junior_admin_access()
async def unban(ctx: commands.Context, user_id: int):

    try:

        user = await bot.fetch_user(user_id)

        await ctx.guild.unban(user)

        embed = discord.Embed(
            title="✅ User Unbanned",
            color=discord.Color.green()
        )

        embed.add_field(
            name="User",
            value=f"{user} (`{user.id}`)",
            inline=False
        )

        embed.add_field(
            name="Moderator",
            value=ctx.author.mention,
            inline=False
        )

        await ctx.send(embed=embed)

    except discord.NotFound:

        await ctx.send("❌ No banned user found with that ID.")

    except discord.Forbidden:

        await ctx.send("❌ I don't have permission to unban users.")

    except Exception as e:

        await ctx.send(f"❌ {e}")

@bot.command(name="purge", help="Bulk delete messages. Usage: ?purge <count>")
@has_full_access()
async def purge(ctx: commands.Context, count: int):
    if count < 1:
        await ctx.send("❌ Parameter constraint failed. Count value must be >= 1.")
        return
    deleted = await ctx.channel.purge(limit=count + 1)  # +1 to also remove the ?purge command message
    await ctx.send(f"🗑️ Bulk cleanup sweep over. Extinguished `{len(deleted) - 1}` old trace packages.", delete_after=5)

# ==============================================================================
# 11. INFORMATIONAL LAYERS, METRICS & SERVER STATISTICS
# ==============================================================================
@bot.command(name="userinfo", help="Show a member's profile info. Usage: ?userinfo [@member]")
async def userinfo(ctx: commands.Context, member: discord.Member = None):
    member = member or ctx.author
    roles_str = ", ".join([r.mention for r in member.roles[1:15]]) or "No custom roles structural overrides found."
    embed = discord.Embed(title=f"Identity Profile: {member.name}", color=member.color)
    embed.add_field(name="Network Identity Handle", value=f"`{member.id}`", inline=True)
    embed.add_field(name="Account Spawned", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Gateway Node Entry", value=member.joined_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Assigned Security Arrays", value=roles_str, inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="help")
@has_full_access()
async def help_command(ctx):

    embed = discord.Embed(
        title="🤖 Staff Commands",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="Moderation",
        value="""
`?warn`
`?warns`
`?mute`
`?unmute`
`?kick`
`?ban`
`?unban`
`?role`
`?snipe`
`?history`
`?av`
`?afkclear`
""",
        inline=False
    )
    await ctx.send(embed=embed)

@bot.command(name="serverinfo", help="Show server statistics.")
async def serverinfo(ctx: commands.Context):
    g = ctx.guild
    embed = discord.Embed(title=f"Architecture Report: {g.name}", color=discord.Color.blue())
    embed.add_field(name="Structural ID", value=f"`{g.id}`", inline=True)
    embed.add_field(name="Primary Owner Node", value=g.owner.mention if g.owner else "Null Reference", inline=True)
    embed.add_field(name="Population Registry", value=f"Total: `{g.member_count}`", inline=True)
    embed.add_field(name="Channel Subsections", value=f"Text: `{len(g.text_channels)}` | Voice: `{len(g.voice_channels)}`", inline=False)
    if g.icon: embed.set_thumbnail(url=g.icon.url)
    await ctx.send(embed=embed)

# ==============================================================================
# 13. RUNTIME KEEP-ALIVE SYSTEM ENGINE
# ==============================================================================
app = Flask('')

@app.route('/')
def home():
    return "Dhawal Master Core Architecture Operational 24/7!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_web_server)
    t.start()

# ==============================================================================
# 14. BOOT ENGINE INSTANTIATOR
# ==============================================================================
if __name__ == "__main__":

    files = [
        "edit_logs.json",
        "snipe.json",
        "warns.json"
    ]

    for file in files:
        if not os.path.exists(file):
            with open(file, "w") as f:
                f.write("{}")

    keep_alive()
    bot.run(TOKEN)