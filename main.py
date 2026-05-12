import discord
from discord.ext import commands
from discord.utils import get
import asyncio

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.messages = True

bot = commands.Bot(command_prefix="+", intents=intents)

blacklist = set()
locked_names = {} # user_id: nickname
muted_role_name = "Muted"
sniped_messages = {}

@bot.event
async def on_ready():
    print(f"✅ Connecté en tant que {bot.user}")

@bot.event
async def on_member_update(before, after):
    if after.id in locked_names:
        target_name = locked_names[after.id]
        if after.display_name != target_name:
            try:
                await after.edit(nick=target_name, reason="Nom verrouillé (lockname)")
            except Exception as e:
                print(f"❌ Impossible de remettre le pseudo verrouillé pour {after}: {e}")

@bot.event
async def on_message_delete(message):
    sniped_messages[message.channel.id] = (message.author, message.content)

# ---------------- SNIPE ----------------
@bot.command()
@commands.has_permissions(administrator=True)
async def snipe(ctx):
    msg = sniped_messages.get(ctx.channel.id)
    if msg is None:
        await ctx.send("Rien à sniper ici.")
    else:
        author, content = msg
        await ctx.send(f"Dernier message supprimé par {author}: {content}")

# ----------- BLACKLIST & BAN -----------
async def get_target_member(ctx, target: str = None):
    if ctx.message.reference:
        msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        return msg.author
    if target:
        try:
            return await commands.MemberConverter().convert(ctx, target)
        except commands.MemberNotFound:
            return None
    return None

async def get_target_user(ctx, target: str = None):
    if ctx.message.reference:
        msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        return msg.author
    if target:
        if target.isdigit():
            user_id = int(target)
            return bot.get_user(user_id) or await bot.fetch_user(user_id)
        try:
            return await commands.UserConverter().convert(ctx, target)
        except commands.UserNotFound:
            return None
    return None

@bot.event
async def on_member_join(member):
    if member.id in blacklist:
        try:
            await member.ban(reason="Auto-ban: Blacklisted user")
            print(f"✅ {member} banni automatiquement (blacklist).")
        except Exception as e:
            print(f"❌ Erreur lors du ban auto de {member}: {e}")

@bot.command()
@commands.has_permissions(administrator=True)
async def bl(ctx, target: str = None):
    if target and target.lower() == "all":
        count = 0
        for member in ctx.guild.members:
            if not member.bot and not member.guild_permissions.administrator:
                blacklist.add(member.id)
                try:
                    await ctx.guild.ban(member, reason="Blacklist auto-ban")
                    count += 1
                except Exception:
                    pass
        await ctx.send(f"{count} membres ajoutés à la blacklist et bannis.")
        return

    user = await get_target_user(ctx, target)
    if not user:
        await ctx.send("Utilisateur introuvable (ID, mention ou réponse).")
        return

    blacklist.add(user.id)
    try:
        await ctx.guild.ban(user, reason="Blacklist auto-ban")
        await ctx.send(f"{user} ajouté à la blacklist et banni.")
    except Exception as e:
        await ctx.send(f"{user} blacklisté mais impossible de le bannir : {e}")

@bot.command()
@commands.has_permissions(administrator=True)
async def unbl(ctx, target: str = None):
    user = await get_target_user(ctx, target)
    if not user:
        await ctx.send("Utilisateur introuvable (ID, mention ou réponse).")
        return

    if user.id not in blacklist:
        await ctx.send(f"L'ID `{user.id}` n'était pas dans la blacklist.")
        return

    blacklist.remove(user.id)

    banned_users = await ctx.guild.bans()
    ban_entry = discord.utils.find(lambda e: e.user.id == user.id, banned_users)
    if ban_entry:
        try:
            await ctx.guild.unban(ban_entry.user)
            await ctx.send(f"L'utilisateur (ID: `{user.id}`) a été retiré de la blacklist et débanni.")
        except Exception as e:
            await ctx.send(f"Retiré de la blacklist mais impossible de débannir : {e}")
    else:
        await ctx.send(f"L'ID `{user.id}` a été retiré de la blacklist.")

# ---------------- BAN / UNBAN ----------------
@bot.command()
@commands.has_permissions(administrator=True)
async def ban(ctx, target: str = None):
    user = await get_target_user(ctx, target)
    if not user:
        await ctx.send("Utilisateur introuvable (ID, mention ou réponse).")
        return

    try:
        await ctx.guild.ban(user)
        await ctx.send(f"{user} a été banni.")
    except Exception as e:
        await ctx.send(f"Erreur lors du ban : {e}")

@bot.command()
@commands.has_permissions(administrator=True)
async def unban(ctx, target: str = None):
    user = await get_target_user(ctx, target)
    if not user:
        await ctx.send("Utilisateur introuvable (ID, mention ou réponse).")
        return

    try:
        await ctx.guild.unban(user)
        await ctx.send(f"{user} (ID: `{user.id}`) a été débanni.")
    except discord.NotFound:
        await ctx.send("Cet utilisateur n'est pas banni ou n'existe pas.")
    except Exception as e:
        await ctx.send(f"Erreur lors du unban : {e}")

@bot.command()
@commands.has_permissions(administrator=True)
async def unbanall(ctx):
    try:
        banned_users = await ctx.guild.bans()
        if not banned_users:
            await ctx.send("Il n'y a aucun utilisateur banni.")
            return

        count = 0
        for ban_entry in banned_users:
            try:
                await ctx.guild.unban(ban_entry.user)
                count += 1
            except Exception:
                pass
        await ctx.send(f"✅ {count} utilisateurs ont été débannis.")
    except Exception as e:
        await ctx.send(f"Erreur lors du unbanall : {e}")

# ---------------- CLEAR ----------------
@bot.command()
@commands.has_permissions(administrator=True)
async def clear(ctx, amount: int):
    if amount < 1:
        await ctx.send("Le nombre doit être supérieur à 0.")
        return
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"{len(deleted)-1} messages supprimés.", delete_after=5)

@bot.command()
@commands.has_permissions(administrator=True)
async def clearuser(ctx, target: str = None, limit: int = 100):
    member = await get_target_member(ctx, target)
    if not member:
        await ctx.send("Utilisateur introuvable sur le serveur (mention ou réponse).")
        return

    def is_user(msg):
        return msg.author == member
    deleted = await ctx.channel.purge(limit=limit, check=is_user)
    await ctx.send(f"{len(deleted)} messages supprimés de {member.display_name}.", delete_after=5)

# ---------------- MUTE / UNMUTE ----------------
@bot.command()
@commands.has_permissions(administrator=True)
async def mute(ctx, target: str = None, *, reason: str = "Aucune raison fournie"):
    user = await get_target_member(ctx, target)
    if not user:
        await ctx.send("Utilisateur introuvable sur le serveur (mention ou réponse).")
        return

    role = get(ctx.guild.roles, name=muted_role_name)
    if role is None:
        role = await ctx.guild.create_role(name=muted_role_name)
        for channel in ctx.guild.channels:
            if isinstance(channel, discord.TextChannel):
                await channel.set_permissions(role, send_messages=False, add_reactions=False)
            elif isinstance(channel, discord.VoiceChannel):
                await channel.set_permissions(role, connect=False, speak=False)
    
    await user.add_roles(role, reason=reason)
    await ctx.send(f"{user.mention} a été réduit au silence (Textuel + Vocal).")

@bot.command()
@commands.has_permissions(administrator=True)
async def unmute(ctx, target: str = None):
    user = await get_target_member(ctx, target)
    if not user:
        await ctx.send("Utilisateur introuvable sur le serveur (mention ou réponse).")
        return

    role = get(ctx.guild.roles, name=muted_role_name)
    if role is None:
        await ctx.send("Le rôle mute n'existe pas.")
        return
    await user.remove_roles(role)
    await ctx.send(f"{user.mention} a été unmute.")

@bot.command()
@commands.has_permissions(administrator=True)
async def unmuteall(ctx):
    role = get(ctx.guild.roles, name=muted_role_name)
    if role is None:
        await ctx.send("Le rôle mute n'existe pas.")
        return
    
    count = 0
    for member in ctx.guild.members:
        if role in member.roles:
            try:
                await member.remove_roles(role)
                count += 1
            except Exception:
                pass
    await ctx.send(f"✅ {count} membres ont été démute.")

# ---------------- LOCKNAME / UNLOCKNAME ----------------
@bot.command()
@commands.has_permissions(administrator=True)
async def lockname(ctx, target: str = None, *, name: str):
    user = await get_target_member(ctx, target)
    if not user:
        await ctx.send("Utilisateur introuvable sur le serveur (mention ou réponse).")
        return

    locked_names[user.id] = name
    try:
        await user.edit(nick=name, reason="Lockname command")
        await ctx.send(f"🔒 Le pseudo de {user.mention} est maintenant verrouillé sur : `{name}`.")
    except Exception as e:
        await ctx.send(f"Le pseudo a été enregistré mais impossible de changer son pseudo actuel (permissions ?) : {e}")

@bot.command()
@commands.has_permissions(administrator=True)
async def unlockname(ctx, target: str = None):
    user = await get_target_member(ctx, target)
    if not user:
        await ctx.send("Utilisateur introuvable sur le serveur (mention ou réponse).")
        return

    if user.id in locked_names:
        del locked_names[user.id]
        await ctx.send(f"🔓 Le pseudo de {user.mention} est maintenant déverrouillé.")
    else:
        await ctx.send(f"{user.mention} n'avait pas de pseudo verrouillé.")

# ---------------- VE ----------------
@bot.command()
async def ve(ctx, target: str = None):
    if not (ctx.author.guild_permissions.administrator or ctx.author == ctx.guild.owner):
        await ctx.send("❌ Tu n'as pas la permission d'utiliser cette commande.")
        return

    user = await get_target_member(ctx, target)
    if not user:
        await ctx.send("Utilisateur introuvable (mention ou réponse).")
        return

    role = ctx.guild.get_role(1503489020725039195)
    if role is None:
        await ctx.send("Le rôle est introuvable sur ce serveur.")
        return

    await user.add_roles(role)
    await ctx.send(f"{user.mention} a reçu le rôle {role.name}.")

# ---------------- RENEW ----------------
@bot.command()
@commands.has_permissions(administrator=True)
async def renew(ctx):
    channel = ctx.channel
    
    # On récupère les paramètres essentiels
    name = channel.name
    category = channel.category
    position = channel.position
    overwrites = channel.overwrites
    topic = channel.topic
    nsfw = channel.is_nsfw()
    slowmode = channel.slowmode_delay
    permissions_synced = channel.permissions_synced

    # On recrée le salon
    new_channel = await ctx.guild.create_text_channel(
        name=name,
        category=category,
        overwrites=overwrites,
        topic=topic,
        nsfw=nsfw,
        slowmode_delay=slowmode,
        position=position
    )
    
    # On supprime l'ancien
    await channel.delete()
    
    # Petit message dans le nouveau salon
    await new_channel.send(f"✨ Salon renouvelé par {ctx.author.mention}. Tous les messages ont été effacés.")

# ---------------- LOCK / UNLOCK ----------------
@bot.command()
@commands.has_permissions(administrator=True)
async def lock(ctx, *, channel_ref: str):
    channel = ctx.channel if channel_ref.lower() == "here" \
        else discord.utils.get(ctx.guild.text_channels, name=channel_ref.strip("#"))
    if not channel:
        await ctx.send("Salon introuvable.")
        return

    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send(f"🔒 {channel.mention} est maintenant verrouillé pour les membres.")

@bot.command()
@commands.has_permissions(administrator=True)
async def unlock(ctx, *, channel_ref: str):
    channel = ctx.channel if channel_ref.lower() == "here" \
        else discord.utils.get(ctx.guild.text_channels, name=channel_ref.strip("#"))
    if not channel:
        await ctx.send("Salon introuvable.")
        return

    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = True
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send(f"🔓 {channel.mention} est maintenant déverrouillé pour les membres.")

# ------------- ANTI-LIEN INVITE DISCORD -------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if "discord.gg/" in message.content or "discord.com/invite/" in message.content:
        if not message.author.guild_permissions.administrator:
            await message.delete()
            await message.channel.send(
                f"{message.author.mention} : les liens d'invitation Discord sont interdits ici.",
                delete_after=5
            )
            return

    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Tu n'as pas la permission d'utiliser cette commande.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Argument manquant. Vérifie la syntaxe de la commande.")

import os

bot.run(os.getenv("TOKEN"))
