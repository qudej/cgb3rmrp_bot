import discord
from datetime import datetime, timedelta
from config import *

def is_senior_staff(member: discord.Member) -> bool:
    if member.guild_permissions.administrator: return True
    for role in member.roles:
        if role.id in SENIOR_STAFF_ROLES: return True
    return False

def is_senior_dept_staff(member: discord.Member) -> bool:
    if member.guild_permissions.administrator: return True
    for role in member.roles:
        if role.id in SENIOR_DEPT_ROLES: return True
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

async def apply_rank_roles(admin_user: discord.Member, member: discord.Member, new_rank_data: dict) -> bool:
    
    if not can_target_member(admin_user, member):
        return False
    
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
    
    # Сохраняем никнейм до того, как мы его изменим, чтобы вывести в ЧС без пинга
    plain_user_str = member.display_name if member else f"{name} | {static}"
    
    if not member: 
        mention_str = f"<@{target_user_id}>"

    if member and not can_target_member(admin_user, member):
        await interaction.response.send_message(
            "❌ Вы не можете уволить этого сотрудника: его роль выше или равна вашей, либо это владелец сервера, либо вы пытаетесь уволить себя.",
            ephemeral=True
        )
        return

    # Снимаем все роли и выдаем роль уволенного
    if member:
        target_role = guild.get_role(ROLE_AFTER_DISMISSAL)
        if target_role:
            try: await member.add_roles(target_role)
            except discord.Forbidden: pass

        for r in member.roles:
            if r.id != guild.id and not r.managed and r.id != ROLE_AFTER_DISMISSAL:
                try: await member.remove_roles(r)
                except discord.Forbidden: pass 
                
        # Меняем ник уволенному
        try: 
            new_nick = f"УВ | {name} | {static}"
            await member.edit(nick=new_nick[:32])
        except discord.Forbidden: 
            pass

        if bl_reason: # Если есть причина ЧС, значит увольнение идет с ЧС
            bl_role = guild.get_role(BLACKLIST_ROLE_ID)
            if bl_role:
                try: await member.add_roles(bl_role)
                except discord.Forbidden: pass

    current_date = datetime.now(msk_tz)
    
    # Флаг: выдан ли ЧС?
    is_blacklist = bool(bl_reason)
    chs_until_str, duration_str = "", ""

    if is_blacklist:
        if not bl_duration: bl_duration = "14" # По умолчанию 14 дней
        try:
            days = int(bl_duration)
            chs_until = current_date + timedelta(days=days)
            chs_until_str = chs_until.strftime("%d.%m.%Y %H:%M")
            duration_str = f"{days} дней"
        except ValueError:
            chs_until_str = bl_duration
            duration_str = bl_duration

    # 1. Лог кадрового аудита (Увольнение)
    log_channel = guild.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        desc = (
            f"👤 **Уволен:** {mention_str}\n"
            f"🧾 **Оформил:** {admin_user.mention}\n"
            f"📑 **Уволен согласно:** {report_link}\n\n"
            f"📝 **Причина:** {dismiss_reason}\n"
            f"📅 **Дата:** {current_date.strftime('%d.%m.%Y %H:%M')}"
        )
        
        # Добавляем строку про ЧС только если ЧС действительно выдан!
        if is_blacklist:
            desc += f"\n⛔ **ЧС до:** {chs_until_str}"

        embed_audit = discord.Embed(
            title="📕 Кадровый аудит: Увольнение",
            description=desc,
            color=discord.Color.dark_red()
        )
        await log_channel.send(embed=embed_audit)

    # 2. Лог ЧС
    if is_blacklist:
        bl_channel = guild.get_channel(BLACKLIST_CHANNEL_ID)
        if bl_channel:
            bl_desc = (
                f"**Оформил:**\n{admin_user.mention}\n\n"
                f"**Внесен в ЧС:**\n{plain_user_str}\n\n"
                f"**Длительность:**\n{duration_str}\n\n"
                f"**Причина внесения в ЧС:**\n{bl_reason}"
            )
            
            if report_link and report_link != "Контекстное меню":
                bl_desc += f"\n\n**Уволен согласно:**\n{report_link}"

            embed_bl = discord.Embed(
                title="⛔ Черный список. Пополнение",
                description=bl_desc,
                color=discord.Color.dark_red() 
            )
            
            # Пингуем администраторов
            mentions_str = " ".join([f"<@&{r_id}>" for r_id in BLACKLIST_PING_ROLES])
            await bl_channel.send(content=mentions_str, embed=embed_bl)

def can_target_member( user: discord.Member, target: discord.Member) -> bool:
    if target.id == target.guild.owner_id: return False
    if user.id == target.id: return False
    if target.top_role >= user.top_role: return False
    return True
