import discord
import re
from datetime import datetime
from config import *
from utils import is_senior_staff, extract_user_data, execute_dismissal

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
        embed.add_field(name="📋 Результат", value=f"Уволил с ЧС: {interaction.user.mention}", inline=False)
        
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
        embed.add_field(name="📋 Результат", value=f"Уволил: {interaction.user.mention}", inline=False)
        
        self.clear_items()
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Уволить с ЧС", style=discord.ButtonStyle.gray, custom_id="dismiss_bl_btn")
    async def dismiss_bl_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = interaction.message.embeds[0]
        user_id = int(embed.footer.text.replace("ID пользователя: ", ""))
        fields = {f.name: f.value for f in embed.fields}
        reason = fields.get("Причина", "Не указана")
        await interaction.response.send_modal(AdminBlacklistModal(user_id, interaction.message, reason, self))

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
        embed.add_field(name="📋 Результат", value=f"Принял: {interaction.user.mention}", inline=False)
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
        embed.add_field(name="📋 Результат", value=f"Отклонил: {interaction.user.mention}", inline=False)
        self.clear_items()
        await interaction.message.edit(embed=embed, view=self)

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
        embed = discord.Embed(title="⏳ Заявление на увольнение", color=discord.Color.orange())
        embed.add_field(name="Сотрудник", value=interaction.user.mention, inline=False)
        embed.add_field(name="Причина", value=self.reason_field.value, inline=False)
        embed.set_footer(text=f"ID пользователя: {interaction.user.id}")
        
        mentions_str = " ".join([f"<@&{r_id}>" for r_id in PING_RESIGNATION])
        if channel:
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