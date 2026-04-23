import discord
from datetime import datetime, timedelta
from config import *

def is_senior_staff(member: discord.Member) -> bool:
    if member.guild_permissions.administrator: return True
    for role in member.roles:
        if role.id in SENIOR_STAFF_ROLES: return True
    return False

def extract_user_data(member: discord.Member):
    name, static = "Неизвестно", "000-000"
    if member:
        nick_parts = member.display_name.split(" | ")
        if len(nick_parts) >= 3:
            name, static = nick_parts[1].strip(), nick_parts[2].strip()
        else:
            name = member.display_name
    mention_str = member.mention if member else "Неизвестный"
    return mention_str, name, static

async def apply_rank_roles(member: discord.Member, new_rank_data: dict) -> bool:
    guild = member.guild
    all_faction_role_ids = set()
    for r in RANK_SYSTEM:
        all_faction_role_ids.add(r["main_role"])
        for extra in r.get("extra_roles",[]): 
            all_faction_role_ids.add(extra)
            
    for sr_id in SENIOR_DEPT_ROLES.values():
        all_faction_role_ids.add(sr_id)

    roles_to_remove =[r for r in member.roles if r.id in all_faction_role_ids]
    if roles_to_remove:
        try: await member.remove_roles(*roles_to_remove)
        except discord.Forbidden: return False

    roles_to_add =[guild.get_role(new_rank_data["main_role"])]
    for extra_id in new_rank_data.get("extra_roles",[]): 
        roles_to_add.append(guild.get_role(extra_id))
        
    if new_rank_data.get("is_senior", False):
        user_dept = None
        for dept_name, role_id in DEPARTMENTS_ROLES.items():
            if any(r.id == role_id for r in member.roles):
                user_dept = dept_name
                break
        if user_dept and user_dept in SENIOR_DEPT_ROLES:
            roles_to_add.append(guild.get_role(SENIOR_DEPT_ROLES[user_dept]))

    roles_to_add =[r for r in roles_to_add if r is not None]
    try:
        await member.add_roles(*roles_to_add)
        if "set_prefix" in new_rank_data:
            _, name, static = extract_user_data(member)
            new_nick = f"{new_rank_data['set_prefix']} | {name} | {static}"
            try: await member.edit(nick=new_nick[:32])
            except discord.Forbidden: pass
        return True
    except discord.Forbidden:
        return False

async def execute_dismissal(guild, interaction, target_user_id, admin_user, dismiss_reason, bl_reason=None, bl_duration=None, report_link="Нет ссылки"):
    member = guild.get_member(target_user_id)
    mention_str, name, static = extract_user_data(member)
    if not member: mention_str = f"<@{target_user_id}>"

    if member:
        target_role = guild.get_role(ROLE_AFTER_DISMISSAL)
        if target_role:
            try: await member.add_roles(target_role)
            except discord.Forbidden: pass

        for r in member.roles:
            if r.id != guild.id and not r.managed and r.id != ROLE_AFTER_DISMISSAL:
                try: await member.remove_roles(r)
                except discord.Forbidden: pass 
                
        try: 
            new_nick = f"УВ | {name} | {static}"
            await member.edit(nick=new_nick[:32])
        except discord.Forbidden: 
            pass

    current_date = datetime.now(msk_tz)
    chs_until_str, duration_str = "Нет", "0 дней"

    if bl_reason and bl_duration:
        try:
            days = int(bl_duration)
            chs_until = current_date + timedelta(days=days)
            chs_until_str = chs_until.strftime("%d.%m.%Y %H:%M")
            duration_str = f"{days} дней"
        except ValueError:
            chs_until_str = bl_duration
            duration_str = bl_duration

    log_channel = guild.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        embed_audit = discord.Embed(
            title="📕 Кадровый аудит: Увольнение",
            description=(
                f"👤 **Уволен:** {mention_str}\n"
                f"🧾 **Оформил:** {admin_user.mention}\n"
                f"📑 **Уволен согласно:** {report_link}\n\n"
                f"📝 **Причина:** {dismiss_reason}\n"
                f"📅 **Дата:** {current_date.strftime('%d.%m.%Y %H:%M')}\n"
                f"⛔ **ЧС до:** {chs_until_str}"
            ),
            color=discord.Color.dark_red()
        )
        await log_channel.send(embed=embed_audit)

    if bl_reason:
        bl_channel = guild.get_channel(BLACKLIST_CHANNEL_ID)
        if bl_channel:
            embed_bl = discord.Embed(
                title="⛔ Черный список. Пополнение",
                description=(
                    f"**Оформил:**\n{admin_user.mention}\n\n"
                    f"**Внесен в ЧС:**\n{mention_str}\n\n"
                    f"**Длительность:**\n{duration_str}\n\n"
                    f"**Причина внесения в ЧС:**\n{bl_reason}\n\n"
                    f"**Уволен согласно:**\n{report_link}"
                ),
                color=discord.Color.default()
            )
            await bl_channel.send(embed=embed_bl)