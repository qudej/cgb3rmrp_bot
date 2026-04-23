import os
import re
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# ==============================================================================
#                               НАСТРОЙКИ БОТА
# ==============================================================================

# --- ОСНОВНЫЕ РОЛИ ---
SENIOR_STAFF_ROLES = [1496662038716612618] # Роли старшего состава
ROLES_EMPLOYMENT =[1496632562385162331, 1496632517300850860] # Выдаются при трудоустройстве
ROLES_STATE_EMP =[1496632591556804810] # Выдаются гос. сотрудникам
ROLE_AFTER_DISMISSAL = 1496793118312501298 # При увольнении

# --- КАНАЛЫ ЗАЯВОК И ЛОГОВ (КАДРОВЫЙ АУДИТ) ---
REQUESTS_CHANNEL_ID = 1496612028490453016 # Сюда падают заявки на трудоустройство
DISMISS_REQUESTS_CHANNEL_ID = 1496851256063561788 # Заявки на увольнение
LOG_CHANNEL_ID = 1496647709443227828 # Логи кадрового аудита
BLACKLIST_CHANNEL_ID = 1496793337686917291 # Логи Черного списка

# --- НАСТРОЙКИ ВЗЫСКАНИЙ ---
PUNISHMENT_SETUP_CHANNEL_ID = 1496792662865481810 # Канал взысканий
PUNISHMENT_LOG_CHANNEL_ID = 1496792662865481810 # Канал логов взысканий
PUNISHMENTS_ROLES = {
    "Предупреждение 1/2": 1496793566326816868,
    "Выговор 1/2": 1496793631976063017
}

# --- НАСТРОЙКИ ПОСТАВОК ---
SUPPLY_SETUP_CHANNEL_ID = 1496792637313781801 # Канал для поставок
SUPPLY_LOG_CHANNEL_ID = 1496792637313781801 # Канал запросов поставок 
SUPPLY_PING_ROLE_ID = 1496793925694914651 # Роль для пинга поставщиков
SUPPLY_REPORT_CHANNEL_ID = 1496800374726590545 # отчеты о поставках
CHIEF_DOCTOR_ROLE_ID = 1496800241184407552 # Роль ГВ 
SUPPLY_WORKER_ROLES =[1496793925694914651, 1496820224282984518, 1496820232709341315, 1496820233007140937] # Кто может быть ответственным/помощником

# --- НАСТРОЙКИ ОТДЕЛОВ ---
DEPT_SETUP_CHANNEL_ID = 1496612028490453016 # Канал для заявок в отделы
DEPT_REQUESTS_CHANNEL_ID = 1496612028490453016 # Канал куда падают заявки в отделы
DEPT_PING_ROLES = {
    "БСМП":[1496820224282984518], # Пинг Зав/Зам БСМП 
    "АБ":[1496820232709341315],   # Пинг Зав/Зам АБ 
    "КУЦ": [1496820233007140937]   # Пинг Зав/Зам КУЦ 
}
DEPARTMENTS_ROLES = {
    "О": 1496632517300850860,
    "БСМП": 1496820094649634976, 
    "АБ": 1496820091650703460,   
    "КУЦ": 1496820083081744415   
}
SENIOR_DEPT_ROLES = {
    "БСМП": 1496820483050700800, # Роль Старший БСМП 
    "АБ": 1496820233686487220,   # Роль Старший АБ
    "КУЦ": 1496844304088563733   # Роль Старший КУЦ 
}

# --- ПИНГИ (УПОМИНАНИЯ) ПРИ ЗАЯВКАХ ---
# Укажите ID ролей через запятую, кого нужно тегать при новых заявках:
PING_EMPLOYMENT =[111111111111111, 222222222222222] # Зав. отделением и Зам. зав. отделением
PING_STATE_EMP =[333333333333333, 444444444444444] # Глав. Врач, Зам. Глав. Врача
PING_RESIGNATION =[1111, 2222, 3333, 4444] # Глав. Врач, Зам. Глав. Врача, Зав. отделением, Зам. зав.

# --- ПРОЧИЕ НАСТРОЙКИ ---
DEFAULT_EMPLOYMENT_RANK = "Водитель скорой помощи"
BOT_PREFIX = "!"
msk_tz = timezone(timedelta(hours=3))

# === СИСТЕМА РАНГОВ ===
RANK_SYSTEM =[
    {"rank_num": 1, "name": "Водитель скорой помощи", "main_role": 1496632562385162331, "extra_roles": [], "is_senior": False},
    {"rank_num": 2, "name": "Фармацевт", "main_role": 1496641752692690964, "extra_roles":[], "is_senior": False},
    {"rank_num": 3, "name": "Санитар", "main_role": 1496641717657538560, "extra_roles":[1496794566458871808], "is_senior": False, "set_prefix": "ВБО"},
    {"rank_num": 4, "name": "Фельдшер", "main_role": 1496641642516451468, "extra_roles":[], "is_senior": False},
    {"rank_num": 5, "name": "Ординатор 1-го года", "main_role": 321, "extra_roles":[], "is_senior": False},
    {"rank_num": 6, "name": "Ординатор 2-го года", "main_role": 321, "extra_roles":[], "is_senior": False},
    {"rank_num": 7, "name": "Врач второй категории", "main_role": 321, "extra_roles":[], "is_senior": True},
    {"rank_num": 8, "name": "Врач первой категории", "main_role": 321, "extra_roles":[], "is_senior": True},
    {"rank_num": 9, "name": "Врач высшей категории", "main_role": 321, "extra_roles":[], "is_senior": True}
]

# ==============================================================================
#                               ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==============================================================================

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
                
        # Смена никнейма при увольнении
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


# ==============================================================================
#                                КЛАСС БОТА
# ==============================================================================

class MyBot(commands.Bot):
    async def setup_hook(self):
        self.add_view(RoleRequestView())
        self.add_view(AdminReviewView())
        self.add_view(AdminDismissalReviewView())
        self.add_view(PunishmentSetupView())
        self.add_view(SupplySetupView())
        self.add_view(SupplyRequestControlsView())
        self.add_view(DepartmentSetupView())
        self.add_view(DepartmentReviewView())
        await self.tree.sync()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = MyBot(command_prefix=BOT_PREFIX, intents=intents)


# ==============================================================================
#                                ЗАЯВКИ В ОТДЕЛЫ
# ==============================================================================

class DepartmentReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not is_senior_staff(interaction.user):
            await interaction.response.send_message("❌ Это действие доступно только Старшему Составу.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Одобрить", style=discord.ButtonStyle.green, custom_id="dept_accept_btn")
    async def accept_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = interaction.message.embeds[0]
        
        dept_name = "О"
        if "БСМП" in embed.title: dept_name = "БСМП"
        elif "АБ" in embed.title: dept_name = "АБ"
        elif "КУЦ" in embed.title: dept_name = "КУЦ"

        user_id = int(embed.footer.text.replace("ID пользователя: ", ""))
        member = interaction.guild.get_member(user_id)

        if member:
            _, name, static = extract_user_data(member)
            new_nick = f"{dept_name} | {name} | {static}"
            try: await member.edit(nick=new_nick[:32])
            except discord.Forbidden: pass

            roles_to_remove =[]
            for d, r_id in DEPARTMENTS_ROLES.items():
                r = interaction.guild.get_role(r_id)
                if r and r in member.roles: roles_to_remove.append(r)
                    
            for d, r_id in SENIOR_DEPT_ROLES.items():
                r = interaction.guild.get_role(r_id)
                if r and r in member.roles: roles_to_remove.append(r)

            roles_to_add =[]
            role_to_add = interaction.guild.get_role(DEPARTMENTS_ROLES.get(dept_name, 0))
            if role_to_add: roles_to_add.append(role_to_add)

            user_roles_ids = [r.id for r in member.roles]
            is_senior = False
            for rank_data in RANK_SYSTEM:
                if rank_data["main_role"] in user_roles_ids and rank_data.get("is_senior", False):
                    is_senior = True
                    break
            
            if is_senior:
                new_senior_role = interaction.guild.get_role(SENIOR_DEPT_ROLES.get(dept_name, 0))
                if new_senior_role: roles_to_add.append(new_senior_role)

            try:
                if roles_to_remove: await member.remove_roles(*roles_to_remove)
                if roles_to_add: await member.add_roles(*roles_to_add)
            except discord.Forbidden: pass

        embed.title = embed.title.replace("⏳", "✅").replace("на рассмотрении", "одобрена")
        embed.color = discord.Color.green()
        embed.add_field(name="📋", value=f"Одобрил: {interaction.user.mention}", inline=False)
        self.clear_items()
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.red, custom_id="dept_reject_btn")
    async def reject_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = interaction.message.embeds[0]
        embed.title = embed.title.replace("⏳", "❌").replace("на рассмотрении", "отклонена")
        embed.color = discord.Color.red()
        embed.add_field(name="📋", value=f"Отклонил: {interaction.user.mention}", inline=False)
        self.clear_items()
        await interaction.message.edit(embed=embed, view=self)

class DepartmentModal(discord.ui.Modal):
    rank_field = discord.ui.TextInput(label='Должность', required=True)
    doc_field = discord.ui.TextInput(label='Удостоверение (ссылка)', placeholder='Ссылка на скриншот', required=True)

    def __init__(self, dept_name: str):
        super().__init__(title=f'Заявка в {dept_name}')
        self.dept_name = dept_name

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(DEPT_REQUESTS_CHANNEL_ID)
        embed = discord.Embed(title=f"⏳ Заявка в отдел: {self.dept_name} на рассмотрении", color=discord.Color.yellow())
        embed.add_field(name="Кто подал", value=interaction.user.mention, inline=False)
        embed.add_field(name="Должность", value=self.rank_field.value, inline=False)
        embed.add_field(name="Удостоверение", value=self.doc_field.value, inline=False)
        embed.set_footer(text=f"ID пользователя: {interaction.user.id}")
        
        role_ids = DEPT_PING_ROLES.get(self.dept_name,[])
        mentions_str = " ".join([f"<@&{r_id}>" for r_id in role_ids])
        
        if channel:
            await channel.send(content=mentions_str, embed=embed, view=DepartmentReviewView())
        await interaction.response.send_message(f"Ваша заявка в отдел **{self.dept_name}** успешно отправлена!", ephemeral=True)

class DepartmentSetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="БСМП", style=discord.ButtonStyle.blurple, custom_id="setup_dept_bsmp")
    async def bsmp_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DepartmentModal("БСМП"))

    @discord.ui.button(label="АБ", style=discord.ButtonStyle.blurple, custom_id="setup_dept_ab")
    async def ab_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DepartmentModal("АБ"))

    @discord.ui.button(label="КУЦ", style=discord.ButtonStyle.blurple, custom_id="setup_dept_kuc")
    async def kuc_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DepartmentModal("КУЦ"))


# ==============================================================================
#                       МОДАЛЬНЫЕ ОКНА И КНОПКИ УВОЛЬНЕНИЯ
# ==============================================================================

class AdminBlacklistModal(discord.ui.Modal, title="Оформление ЧС"):
    bl_duration = discord.ui.TextInput(label="Длительность (в днях)", placeholder="14", required=True)
    bl_reason = discord.ui.TextInput(label="Причина занесения в ЧС", required=True)

    def __init__(self, target_user_id: int, original_msg: discord.Message, dismiss_reason: str, view: discord.ui.View):
        super().__init__()
        self.target_user_id = target_user_id
        self.original_msg = original_msg
        self.dismiss_reason = dismiss_reason
        self.original_view = view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        report_link = f"[Перейти к заявлению]({self.original_msg.jump_url})"
        await execute_dismissal(interaction.guild, interaction, self.target_user_id, interaction.user, self.dismiss_reason, self.bl_reason.value, self.bl_duration.value, report_link)

        embed = self.original_msg.embeds[0]
        embed.title = "⛔ Заявка рассмотрена: Уволен с ЧС"
        embed.color = discord.Color.dark_grey()
        embed.add_field(name="📋", value=f"Уволил с ЧС: {interaction.user.mention}", inline=False)
        
        self.original_view.clear_items()
        await self.original_msg.edit(embed=embed, view=self.original_view)
        await interaction.followup.send("Сотрудник уволен с занесением в ЧС.", ephemeral=True)

class AdminDismissalReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not is_senior_staff(interaction.user):
            await interaction.response.send_message("❌ Это действие доступно только Старшему Составу.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Уволить", style=discord.ButtonStyle.red, custom_id="dismiss_btn")
    async def dismiss_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = interaction.message.embeds[0]
        user_id = int(embed.footer.text.replace("ID пользователя: ", ""))
        fields = {f.name: f.value for f in embed.fields}
        reason = fields.get("Причина", "Не указана")
        
        report_link = f"[Перейти к заявлению]({interaction.message.jump_url})"
        await execute_dismissal(interaction.guild, interaction, user_id, interaction.user, reason, report_link=report_link)

        embed.title = "✅ Заявка рассмотрена: Уволен"
        embed.color = discord.Color.dark_red()
        embed.add_field(name="📋", value=f"Уволил: {interaction.user.mention}", inline=False)
        
        self.clear_items()
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Уволить с ЧС", style=discord.ButtonStyle.gray, custom_id="dismiss_bl_btn")
    async def dismiss_bl_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = interaction.message.embeds[0]
        user_id = int(embed.footer.text.replace("ID пользователя: ", ""))
        fields = {f.name: f.value for f in embed.fields}
        reason = fields.get("Причина", "Не указана")
        await interaction.response.send_modal(AdminBlacklistModal(user_id, interaction.message, reason, self))

# ==============================================================================
#                                ЗАЯВКИ: ПРИЕМ
# ==============================================================================

class AdminReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not is_senior_staff(interaction.user):
            await interaction.response.send_message("❌ Это действие доступно только Старшему Составу.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Принять", style=discord.ButtonStyle.green, custom_id="admin_accept_btn")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer() 
        embed = interaction.message.embeds[0]
        guild = interaction.guild
        
        try: target_user_id = int(embed.footer.text.replace("ID пользователя: ", ""))
        except: return await interaction.followup.send("❌ Не удалось найти ID пользователя.", ephemeral=True)

        member = guild.get_member(target_user_id)
        if not member: return await interaction.followup.send("❌ Пользователь покинул сервер.", ephemeral=True)

        fields = {f.name: f.value for f in embed.fields}
        target_name = fields.get("Имя Фамилия", "Неизвестно")
        target_static = fields.get("Статический ID", fields.get("Статик", "000-000"))
        
        is_employment = "трудоустройство" in embed.title.lower()

        if is_employment:
            new_nick = f"О | {target_name} | {target_static}"
            roles_to_add =[guild.get_role(r_id) for r_id in ROLES_EMPLOYMENT if guild.get_role(r_id)]
            rank_name = DEFAULT_EMPLOYMENT_RANK
            log_title = "🏷️ Кадровый аудит: Трудоустройство"
        else:
            target_org = fields.get("Организация", "ORG")
            new_nick = f"{target_org} | {target_name} | {target_static}"
            roles_to_add =[guild.get_role(r_id) for r_id in ROLES_STATE_EMP if guild.get_role(r_id)]
            rank_name = fields.get("Должность / Звание", "Не указана")
            log_title = "🏷️ Кадровый аудит: Гос. Сотрудник"

        try:
            await member.edit(nick=new_nick[:32])
            if roles_to_add: await member.add_roles(*roles_to_add)
        except discord.Forbidden: pass

        embed.title = "✅ Заявка одобрена"
        embed.color = discord.Color.green()
        embed.add_field(name="📋", value=f"Принял: {interaction.user.mention}", inline=False)
        
        self.clear_items()
        await interaction.message.edit(embed=embed, view=self)

        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            req_link = f"[Перейти к заявке]({interaction.message.jump_url})"
            log_desc = (
                f"👤 **Новый сотрудник:** {member.mention}\n"
                f"📑 **Принят согласно:** {req_link}\n"
                f"🚑 **Должность:** {rank_name}\n\n"
                f"🤝 **Принял:** {interaction.user.mention}\n"
                f"📅 **Дата:** {datetime.now(msk_tz).strftime('%d.%m.%Y %H:%M')}"
            )
            await log_channel.send(embed=discord.Embed(title=log_title, description=log_desc, color=discord.Color.brand_green()))

    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.red, custom_id="admin_reject_btn")
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = interaction.message.embeds[0]
        embed.title = "❌ Заявка отклонена"
        embed.color = discord.Color.red()
        embed.add_field(name="📋", value=f"Отклонил: {interaction.user.mention}", inline=False)
        self.clear_items()
        await interaction.message.edit(embed=embed, view=self)

# ==============================================================================
#     МОДАЛКИ ПОЛЬЗОВАТЕЛЬСКИХ ФОРМ
# ==============================================================================

class EmploymentModal(discord.ui.Modal, title='Заявка на трудоустройство'):
    name_field = discord.ui.TextInput(label='Имя Фамилия', required=True)
    static_id_field = discord.ui.TextInput(label='Статический ID', placeholder='Например: 123-456', min_length=7, max_length=7, required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        if not re.match(r"^\d{3}-\d{3}$", self.static_id_field.value):
            return await interaction.response.send_message("❌ Ошибка: Статический ID должен быть строго в формате **123-456**!", ephemeral=True)

        channel = interaction.guild.get_channel(REQUESTS_CHANNEL_ID)
        embed = discord.Embed(title="⏳ Новая заявка на трудоустройство на рассмотрении", color=discord.Color.yellow())
        embed.add_field(name="Соискатель", value=interaction.user.mention, inline=False)
        embed.add_field(name="Имя Фамилия", value=self.name_field.value, inline=False)
        embed.add_field(name="Статический ID", value=self.static_id_field.value, inline=False)
        embed.set_footer(text=f"ID пользователя: {interaction.user.id}")
        
        mentions_str = " ".join([f"<@&{r_id}>" for r_id in PING_EMPLOYMENT])
        await channel.send(content=mentions_str, embed=embed, view=AdminReviewView())
        await interaction.response.send_message("Заявка отправлена!", ephemeral=True)

class StateEmployeeModal(discord.ui.Modal, title='Заявка гос. сотрудника'):
    name_field = discord.ui.TextInput(label='Имя Фамилия', required=True)
    static_id_field = discord.ui.TextInput(label='Статический ID', placeholder='Например: 123-456', min_length=7, max_length=7, required=True)
    org_field = discord.ui.TextInput(label='Организация', required=True)
    rank_field = discord.ui.TextInput(label='Должность / Звание', required=True)
    doc_field = discord.ui.TextInput(label='Удостоверение', required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        if not re.match(r"^\d{3}-\d{3}$", self.static_id_field.value):
            return await interaction.response.send_message("❌ Ошибка: Статический ID должен быть строго в формате **123-456**!", ephemeral=True)

        channel = interaction.guild.get_channel(REQUESTS_CHANNEL_ID)
        embed = discord.Embed(title="⏳ Заявка гос. сотрудника на рассмотрении", color=discord.Color.yellow())
        embed.add_field(name="Гос. Сотрудник", value=interaction.user.mention, inline=False)
        embed.add_field(name="Имя Фамилия", value=self.name_field.value, inline=False)
        embed.add_field(name="Статик", value=self.static_id_field.value, inline=False)
        embed.add_field(name="Организация", value=self.org_field.value, inline=False)
        embed.add_field(name="Должность / Звание", value=self.rank_field.value, inline=False)
        embed.add_field(name="Удостоверение", value=self.doc_field.value, inline=False)
        embed.set_footer(text=f"ID пользователя: {interaction.user.id}")
        
        mentions_str = " ".join([f"<@&{r_id}>" for r_id in PING_STATE_EMP])
        await channel.send(content=mentions_str, embed=embed, view=AdminReviewView())
        await interaction.response.send_message("Заявка отправлена!", ephemeral=True)

class ResignationModal(discord.ui.Modal, title='Заявление на увольнение'):
    reason_field = discord.ui.TextInput(label='Причина увольнения', placeholder='ПСЖ / Перевод', required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(DISMISS_REQUESTS_CHANNEL_ID)
        if not channel:
            return await interaction.response.send_message("❌ Ошибка: Канал для заявок на увольнение не настроен.", ephemeral=True)
            
        embed = discord.Embed(title="⏳ Заявление на увольнение", color=discord.Color.orange())
        embed.add_field(name="Сотрудник", value=interaction.user.mention, inline=False)
        embed.add_field(name="Причина", value=self.reason_field.value, inline=False)
        embed.set_footer(text=f"ID пользователя: {interaction.user.id}")
        
        mentions_str = " ".join([f"<@&{r_id}>" for r_id in PING_RESIGNATION])
        await channel.send(content=mentions_str, embed=embed, view=AdminDismissalReviewView())
        await interaction.response.send_message("Заявление на увольнение отправлено старшему составу.", ephemeral=True)

class RoleRequestView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Трудоустройство", style=discord.ButtonStyle.green, custom_id="req_emp")
    async def employment_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EmploymentModal())
    @discord.ui.button(label="Гос. Сотрудник", style=discord.ButtonStyle.blurple, custom_id="req_state_emp")
    async def state_emp_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(StateEmployeeModal())
    @discord.ui.button(label="Увольнение", style=discord.ButtonStyle.red, custom_id="req_resign")
    async def resign_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ResignationModal())

# ==============================================================================
#     ВЗЫСКАНИЯ (КНОПКА И КОНТЕКСТ МЕНЮ)
# ==============================================================================

class PunishmentReasonModal(discord.ui.Modal, title="Выдача взыскания"):
    reason_field = discord.ui.TextInput(label="Причина взыскания (пункт устава)", required=True)

    def __init__(self, target_member: discord.Member, role_id: int, role_name: str):
        super().__init__()
        self.target_member = target_member
        self.role_id = role_id
        self.role_name = role_name

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        role = guild.get_role(self.role_id)
        
        if role:
            try: await self.target_member.add_roles(role)
            except discord.Forbidden: return await interaction.followup.send("❌ Нет прав на выдачу этой роли.", ephemeral=True)

        log_channel = guild.get_channel(PUNISHMENT_LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(title="🔨 Дисциплинарное взыскание", color=discord.Color.dark_orange())
            embed.description = (
                f"**Кто выдал:** {interaction.user.mention}\n"
                f"**Кому:** {self.target_member.mention}\n"
                f"**Взыскание:** {role.mention if role else self.role_name}\n"
                f"**Причина:** {self.reason_field.value}\n\n"
                f"📅 **Дата:** {datetime.now(msk_tz).strftime('%d.%m.%Y %H:%M')}"
            )
            await log_channel.send(embed=embed)
        
        await interaction.followup.send(f"✅ Взыскание успешно выдано {self.target_member.mention}.", ephemeral=True)

class PunishmentBuilderView(discord.ui.View):
    def __init__(self, target_member: discord.Member = None):
        super().__init__(timeout=None)
        self.target_member = target_member
        self.selected_role_id = None
        self.selected_role_name = None
        
        if not target_member:
            self.user_select = discord.ui.UserSelect(placeholder="Выберите сотрудника...", custom_id="punish_user_select")
            self.user_select.callback = self.user_callback
            self.add_item(self.user_select)

        options =[discord.SelectOption(label=name, value=f"{name}|{r_id}") for name, r_id in PUNISHMENTS_ROLES.items()]
        self.role_select = discord.ui.Select(placeholder="Выберите тип взыскания...", options=options, custom_id="punish_role_select")
        self.role_select.callback = self.role_callback
        self.add_item(self.role_select)

    async def user_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.target_member = self.user_select.values[0]

    async def role_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        val = self.role_select.values[0].split("|")
        self.selected_role_name = val[0]
        self.selected_role_id = int(val[1])

    @discord.ui.button(label="Указать причину и выдать", style=discord.ButtonStyle.red, row=2)
    async def submit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.target_member:
            return await interaction.response.send_message("❌ Вы не выбрали сотрудника!", ephemeral=True)
        if not self.selected_role_id:
            return await interaction.response.send_message("❌ Вы не выбрали взыскание!", ephemeral=True)
        await interaction.response.send_modal(PunishmentReasonModal(self.target_member, self.selected_role_id, self.selected_role_name))

class PunishmentSetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Выдать взыскание", style=discord.ButtonStyle.red, custom_id="setup_punish_btn")
    async def punish_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_senior_staff(interaction.user):
            return await interaction.response.send_message("❌ Доступно только Старшему Составу.", ephemeral=True)
        await interaction.response.send_message("Заполните форму ниже:", view=PunishmentBuilderView(), ephemeral=True)

@bot.tree.context_menu(name="Выдать взыскание")
async def context_punishment(interaction: discord.Interaction, member: discord.Member):
    if not is_senior_staff(interaction.user):
        return await interaction.response.send_message("❌ Доступно только Старшему Составу.", ephemeral=True)
    await interaction.response.send_message(f"Выдача взыскания для {member.mention}:", view=PunishmentBuilderView(target_member=member), ephemeral=True)


# ==============================================================================
#        ОТЧЕТЫ О ПОСТАВКАХ
# ==============================================================================

async def send_supply_report(interaction: discord.Interaction, orig_msg: discord.Message, types_str: str, resp_user, help_users, status: str, details=None):
    channel = interaction.guild.get_channel(SUPPLY_REPORT_CHANNEL_ID)
    
    if help_users: helpers_str = ", ".join([u.mention for u in help_users])
    else: helpers_str = "Нет помощников"

    color = discord.Color.green()
    if status == "Выбили": color = discord.Color.red()
    elif status == "Частично успешно": color = discord.Color.orange()

    resp_member = interaction.guild.get_member(resp_user.id)
    resp_mention, resp_name, resp_static = extract_user_data(resp_member) if resp_member else (resp_user.mention, "Неизвестно", "000")

    # Ищем название фракции в оригинальном эмбеде
    faction_str = "Не указана"
    if orig_msg.embeds:
        for line in orig_msg.embeds[0].description.split("\n"):
            if line.startswith("**Фракция:** "):
                faction_str = line.replace("**Фракция:** ", "").strip()
                break

    desc = (
        f"**Ответственный:** {resp_mention}\n"
        f"**Помощники:** {helpers_str}\n"
        f"**Фракция:** {faction_str}\n\n"
        f"**{types_str} — {status}!**\n"
    )
    if details: desc += f"\n**Детали:**\n{details}\n"
    desc += f"\n[🔗 Ссылка на запрос поставки]({orig_msg.jump_url})"

    embed = discord.Embed(title="📊 Отчет о поставке", description=desc, color=color)
    chief_role = interaction.guild.get_role(CHIEF_DOCTOR_ROLE_ID)
    content = chief_role.mention if chief_role else ""

    if channel: await channel.send(content=content, embed=embed)

    orig_embed = orig_msg.embeds[0]
    orig_embed.title = f"📦 Запрос поставки: {status}"
    orig_embed.color = color
    await orig_msg.edit(embed=orig_embed, view=None)

class PartialReportModal(discord.ui.Modal, title="Детали: Частично успешно"):
    details = discord.ui.TextInput(label="Заполнение по примеру: МС - 1/2, ЗМХ - Выбили", style=discord.TextStyle.paragraph, required=True)

    def __init__(self, orig_msg: discord.Message, types_str: str, resp_user, help_users, status: str):
        super().__init__()
        self.orig_msg = orig_msg
        self.types_str = types_str
        self.resp_user = resp_user
        self.help_users = help_users
        self.status = status

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await send_supply_report(interaction, self.orig_msg, self.types_str, self.resp_user, self.help_users, self.status, details=self.details.value)
        await interaction.followup.send("✅ Отчет о поставке успешно сформирован!", ephemeral=True)

class ReportBuilderView(discord.ui.View):
    def __init__(self, status: str, orig_msg: discord.Message, types_str: str):
        super().__init__(timeout=None)
        self.status = status
        self.orig_msg = orig_msg
        self.types_str = types_str

        self.resp_select = discord.ui.UserSelect(placeholder="Кто проводил (Ответственный)", min_values=1, max_values=1, custom_id="rep_resp_sel")
        self.resp_select.callback = self.select_defer
        self.help_select = discord.ui.UserSelect(placeholder="Кто оказывал помощь (можно не выбирать)", min_values=0, max_values=20, custom_id="rep_help_sel")
        self.help_select.callback = self.select_defer

        self.add_item(self.resp_select)
        self.add_item(self.help_select)

    async def select_defer(self, interaction: discord.Interaction):
        await interaction.response.defer()

    @discord.ui.button(label="Продолжить", style=discord.ButtonStyle.green, row=2)
    async def submit_report(self, interaction: discord.Interaction, button: discord.ui.Button):
        resp_users = self.resp_select.values
        help_users = self.help_select.values

        if not resp_users:
            return await interaction.response.send_message("❌ Выберите ответственного сотрудника!", ephemeral=True)

        all_users = list(resp_users) + list(help_users)
        for u in all_users:
            member = interaction.guild.get_member(u.id)
            if member and SUPPLY_WORKER_ROLES:
                has_role = any(r.id in SUPPLY_WORKER_ROLES for r in member.roles)
                if not has_role:
                    return await interaction.response.send_message(f"❌ Ошибка: У сотрудника {member.mention} нет нужной роли для участия в поставках!", ephemeral=True)

        if self.status == "Частично успешно":
            await interaction.response.send_modal(PartialReportModal(self.orig_msg, self.types_str, resp_users[0], help_users, self.status))
        else:
            await interaction.response.defer()
            await send_supply_report(interaction, self.orig_msg, self.types_str, resp_users[0], help_users, self.status, details=None)
            self.clear_items()
            await interaction.edit_original_response(content="✅ Отчет о поставке успешно сформирован!", view=self)

class DenySupplyModal(discord.ui.Modal, title="Отказ в поставке"):
    reason_field = discord.ui.TextInput(label="Причина отказа", placeholder="Например: Склад заполнен / Нет матовозок", required=True)

    def __init__(self, original_msg: discord.Message, view: discord.ui.View):
        super().__init__()
        self.original_msg = original_msg
        self.original_view = view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        embed = self.original_msg.embeds[0]
        embed.title = "📦 Запрос поставки: Отказано"
        embed.color = discord.Color.dark_gray()
        
        # Записываем в эмбед кто отказал и саму причину
        embed.add_field(
            name="📋", 
            value=f"**Отказал:** {interaction.user.mention}\n**Причина:** {self.reason_field.value}", 
            inline=False
        )
        
        self.original_view.clear_items()
        await self.original_msg.edit(embed=embed, view=self.original_view)
        await interaction.followup.send("✅ Запрос на поставку успешно отклонен.", ephemeral=True)

class SupplyRequestControlsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def get_types_str(self, message):
        desc = message.embeds[0].description
        for line in desc.split("\n"):
            if line.startswith("**Тип:** "):
                return line.replace("**Тип:** ", "").strip()
        return "Медикаменты"

    @discord.ui.button(label="Успешно", style=discord.ButtonStyle.green, custom_id="sup_success", row=0)
    async def btn_success(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_senior_staff(interaction.user): return await interaction.response.send_message("❌ Управлять поставками может только Старший Состав.", ephemeral=True)
        types_str = await self.get_types_str(interaction.message)
        await interaction.response.send_message("Сформируйте отчет:", view=ReportBuilderView("Успешно", interaction.message, types_str), ephemeral=True)

    @discord.ui.button(label="Частично успешно", style=discord.ButtonStyle.blurple, custom_id="sup_partial", row=0)
    async def btn_partial(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_senior_staff(interaction.user): return await interaction.response.send_message("❌ Управлять поставками может только Старший Состав.", ephemeral=True)
        types_str = await self.get_types_str(interaction.message)
        await interaction.response.send_message("Сформируйте отчет:", view=ReportBuilderView("Частично успешно", interaction.message, types_str), ephemeral=True)

    @discord.ui.button(label="Выбили", style=discord.ButtonStyle.red, custom_id="sup_fail", row=0)
    async def btn_fail(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_senior_staff(interaction.user): return await interaction.response.send_message("❌ Управлять поставками может только Старший Состав.", ephemeral=True)
        types_str = await self.get_types_str(interaction.message)
        await interaction.response.send_message("Сформируйте отчет:", view=ReportBuilderView("Выбили", interaction.message, types_str), ephemeral=True)

    @discord.ui.button(label="Отказано", style=discord.ButtonStyle.gray, custom_id="sup_deny", row=0)
    async def btn_deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_senior_staff(interaction.user): 
            return await interaction.response.send_message("❌ Управлять поставками может только Старший Состав.", ephemeral=True)
        
        await interaction.response.send_modal(DenySupplyModal(interaction.message, self))

    @discord.ui.button(label="Отменить запрос", style=discord.ButtonStyle.gray, custom_id="sup_cancel", row=1)
    async def btn_cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = interaction.message.embeds[0]
        footer_text = embed.footer.text if embed.footer else ""
        try: requester_id = int(footer_text.replace("ID запросившего: ", ""))
        except: requester_id = 0

        if interaction.user.id != requester_id and not is_senior_staff(interaction.user):
            return await interaction.response.send_message("❌ Только автор запроса (или Старший Состав) может его отменить.", ephemeral=True)

        await interaction.response.defer()
        embed.title = "📦 Запрос поставки: Отменен"
        embed.color = discord.Color.light_grey()
        embed.add_field(name="📋", value=f"Отменил: {interaction.user.mention}", inline=False)
        self.clear_items()
        await interaction.message.edit(embed=embed, view=self)

class SupplyFactionModal(discord.ui.Modal, title="Укажите фракцию"):
    faction_field = discord.ui.TextInput(label="Название фракции", placeholder="Например: ФСБ / УВД / Правительство", required=True)

    def __init__(self, parent_view: discord.ui.View):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(SUPPLY_LOG_CHANNEL_ID)
        if not channel:
            return await interaction.response.send_message("❌ Канал для поставок не настроен.", ephemeral=True)

        types_str = " и ".join(self.parent_view.selected_types)
        color = discord.Color.red() if self.parent_view.selected_urgency == "Срочно" else discord.Color.gold()
        
        embed = discord.Embed(title="📦 Запрос поставки", color=color)
        embed.description = (
            f"**Запросил:** {interaction.user.mention}\n"
            f"**Фракция:** {self.faction_field.value}\n"
            f"**Тип:** {types_str}\n"
            f"**Статус:** {self.parent_view.selected_urgency}\n\n"
            f"📅 {datetime.now(msk_tz).strftime('%d.%m.%Y %H:%M')}"
        )
        embed.set_footer(text=f"ID запросившего: {interaction.user.id}")
        
        ping_role = interaction.guild.get_role(SUPPLY_PING_ROLE_ID)
        content = ping_role.mention if ping_role else ""

        await channel.send(content=content, embed=embed, view=SupplyRequestControlsView())
        
        self.parent_view.clear_items()
        await interaction.response.edit_message(content="✅ Запрос на поставку успешно отправлен!", view=self.parent_view)

class SupplyBuilderView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.selected_types =[]
        self.selected_urgency = None

        type_options =[
            discord.SelectOption(label="ЗМХ", description="Зарайское мед. хранилище"),
            discord.SelectOption(label="МС", description="Медицинские склады")
        ]
        self.type_select = discord.ui.Select(placeholder="Что нужно привезти? (можно оба)", min_values=1, max_values=2, options=type_options)
        self.type_select.callback = self.type_callback
        self.add_item(self.type_select)

        urgency_options =[
            discord.SelectOption(label="Срочно", emoji="🚨"),
            discord.SelectOption(label="По возможности", emoji="⏳")
        ]
        self.urgency_select = discord.ui.Select(placeholder="Выберите срочность...", options=urgency_options)
        self.urgency_select.callback = self.urgency_callback
        self.add_item(self.urgency_select)

    async def type_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.selected_types = self.type_select.values

    async def urgency_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.selected_urgency = self.urgency_select.values[0]

    @discord.ui.button(label="Далее (указать фракцию)", style=discord.ButtonStyle.green, row=2)
    async def submit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_types or not self.selected_urgency:
            return await interaction.response.send_message("❌ Заполните все поля (Тип и Срочность).", ephemeral=True)
        
        # Открываем форму для ввода Фракции
        await interaction.response.send_modal(SupplyFactionModal(self))

class SupplySetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Запросить поставку", style=discord.ButtonStyle.blurple, custom_id="setup_supply_btn", emoji="📦")
    async def supply_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Заполните форму для запроса:", view=SupplyBuilderView(), ephemeral=True)

# ==============================================================================
#     ОСТАЛЬНЫЕ КОНТЕКСТНЫЕ МЕНЮ (Увольнение, Ранг)
# ==============================================================================

class ContextMenuDismissModal(discord.ui.Modal, title="Увольнение сотрудника"):
    reason_field = discord.ui.TextInput(label="Причина увольнения", required=True)
    bl_reason_field = discord.ui.TextInput(label="Причина ЧС (пусто, если без ЧС)", required=False)
    bl_duration_field = discord.ui.TextInput(label="Дней в ЧС", placeholder="14", required=False, default="14")

    def __init__(self, target_member: discord.Member):
        super().__init__()
        self.target_member = target_member

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        bl_reason = self.bl_reason_field.value if self.bl_reason_field.value.strip() else None
        await execute_dismissal(interaction.guild, interaction, self.target_member.id, interaction.user, self.reason_field.value, bl_reason, self.bl_duration_field.value, "Контекстное меню")
        await interaction.followup.send(f"Сотрудник {self.target_member.mention} успешно уволен.", ephemeral=True)

@bot.tree.context_menu(name="Уволить")
async def context_dismiss_user(interaction: discord.Interaction, member: discord.Member):
    if not is_senior_staff(interaction.user):
        return await interaction.response.send_message("❌ У вас нет прав. Доступно только Старшему Составу.", ephemeral=True)
    await interaction.response.send_modal(ContextMenuDismissModal(member))

class SetRankSelect(discord.ui.Select):
    def __init__(self, target_member: discord.Member):
        options =[discord.SelectOption(label=f"[{r['rank_num']}] {r['name']}", value=str(i)) for i, r in enumerate(RANK_SYSTEM[:25])]
        super().__init__(placeholder="Выберите новый ранг...", options=options)
        self.target_member = target_member

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not is_senior_staff(interaction.user):
            return await interaction.followup.send("❌ Доступно только Старшему Составу.")
            
        new_rank_idx = int(self.values[0])
        new_rank = RANK_SYSTEM[new_rank_idx]
        
        success = await apply_rank_roles(self.target_member, new_rank)
        if not success:
            return await interaction.followup.send("❌ Нет прав для изменения ролей.")

        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="🏷️ Кадровый аудит: Изменение ранга",
                description=(f"👤 **Сотрудник:** {self.target_member.mention}\n"
                             f"📈 **Новый ранг:** **{new_rank['name']}**\n\n"
                             f"🤝 **Установил:** {interaction.user.mention}\n"
                             f"📅 **Дата:** {datetime.now(msk_tz).strftime('%d.%m.%Y %H:%M')}"),
                color=discord.Color.blue()
            )
            await log_channel.send(embed=log_embed)
        await interaction.followup.send(f"✅ Ранг сотрудника изменен на **{new_rank['name']}**", ephemeral=True)

class SetRankView(discord.ui.View):
    def __init__(self, target_member: discord.Member):
        super().__init__()
        self.add_item(SetRankSelect(target_member))

@bot.tree.context_menu(name="Установить ранг")
async def context_set_rank(interaction: discord.Interaction, member: discord.Member):
    if not is_senior_staff(interaction.user):
        return await interaction.response.send_message("❌ У вас нет прав.", ephemeral=True)
    await interaction.response.send_message(f"Выберите новый ранг для {member.mention}:", view=SetRankView(member), ephemeral=True)

@bot.tree.context_menu(name="+1 ранг")
async def promote_user(interaction: discord.Interaction, member: discord.Member):
    if not is_senior_staff(interaction.user): return await interaction.response.send_message("❌ У вас нет прав.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    
    user_roles_ids =[r.id for r in member.roles]
    current_rank_idx = -1
    for i, rank_data in enumerate(RANK_SYSTEM):
        if rank_data["main_role"] in user_roles_ids and i > current_rank_idx: current_rank_idx = i

    if current_rank_idx == -1: return await interaction.followup.send(f"❌ {member.mention} не во фракции.")
    if current_rank_idx == len(RANK_SYSTEM) - 1: return await interaction.followup.send(f"❌ Это максимальный ранг.")

    old_rank, new_rank = RANK_SYSTEM[current_rank_idx], RANK_SYSTEM[current_rank_idx + 1]
    
    success = await apply_rank_roles(member, new_rank)
    if not success:
        return await interaction.followup.send("❌ Ошибка: У бота нет прав менять роли этому пользователю.")

    await interaction.followup.send(f"✅ Сотрудник повышен: **{new_rank['name']}**")
    
    log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        log_embed = discord.Embed(
            title="🏷️ Кадровый аудит: Повышение",
            description=(f"👤 **Сотрудник:** {member.mention}\n"
                         f"📈 **Повышение:** {old_rank['name']} ➔ **{new_rank['name']}**\n\n"
                         f"🤝 **Повысил:** {interaction.user.mention}\n"
                         f"📅 **Дата:** {datetime.now(msk_tz).strftime('%d.%m.%Y %H:%M')}"),
            color=discord.Color.blue()
        )
        await log_channel.send(embed=log_embed)

# ==============================================================================
#                   ЗАПУСК
# ==============================================================================

@bot.event
async def on_ready():
    print(f"Бот {bot.user} успешно запущен и синхронизирован!")

@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def setup_command(ctx):
    # 1. Основной эмбед
    embed_hr = discord.Embed(
        title="Кадровый аудит | ЦГБ №3",
        description="Выберите нужный пункт меню ниже, чтобы подать заявку.",
        color=discord.Color.dark_theme()
    )
    await ctx.send(embed=embed_hr, view=RoleRequestView())

    # 2. Эмбед для выдачи Взысканий
    punish_channel = bot.get_channel(PUNISHMENT_SETUP_CHANNEL_ID)
    if punish_channel:
        embed_punish = discord.Embed(
            title="🔨 Управление взысканиями",
            description="Нажмите на кнопку ниже, чтобы выдать дисциплинарное взыскание сотруднику.",
            color=discord.Color.dark_red()
        )
        await punish_channel.send(embed=embed_punish, view=PunishmentSetupView())

    # 3. Эмбед для запроса Поставок
    supply_channel = bot.get_channel(SUPPLY_SETUP_CHANNEL_ID)
    if supply_channel:
        embed_supply = discord.Embed(
            title="📦 Запрос поставок",
            description="Нажмите на кнопку ниже, чтобы запросить поставку медикаментов (ЗМХ / МС).",
            color=discord.Color.dark_blue()
        )
        await supply_channel.send(embed=embed_supply, view=SupplySetupView())

    # 4. Эмбед для заявок в Отделы
    dept_channel = bot.get_channel(DEPT_SETUP_CHANNEL_ID)
    if dept_channel:
        embed_dept = discord.Embed(
            title="🏥 Заявки в отделы",
            description="Выберите отдел, в который хотите подать заявку:",
            color=discord.Color.brand_green()
        )
        await dept_channel.send(embed=embed_dept, view=DepartmentSetupView())

    await ctx.message.delete()

if __name__ == "__main__":
    load_dotenv()
    TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    
    if not TOKEN:
        print("❌ КРИТИЧЕСКАЯ ОШИБКА: Токен не найден! Проверьте файл .env")
    else:
        bot.run(TOKEN)