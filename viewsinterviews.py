import discord
from datetime import datetime
from config import *
from utils import extract_user_data

class InterviewProofModal(discord.ui.Modal, title="Отчет о собеседовании"):
    proof_link = discord.ui.TextInput(label="Доказательства (ссылка)", placeholder="Например: imgur.com/...", required=True)

    def __init__(self, resp_user, help_users, parent_view):
        super().__init__()
        self.resp_user = resp_user
        self.help_users = help_users
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        channel = interaction.guild.get_channel(INTERVIEW_LOG_CHANNEL_ID)
        
        # Формируем список помощников
        helpers_str = ", ".join([u.mention for u in self.help_users]) if self.help_users else "Нет помощников"
        
        # Извлекаем данные ответственного
        resp_member = interaction.guild.get_member(self.resp_user.id)
        resp_mention, resp_name, resp_static = extract_user_data(resp_member) if resp_member else (self.resp_user.mention, "Неизвестно", "000")

        desc = (
            f"**Ответственный:** {resp_mention} | {resp_name} | {resp_static}\n"
            f"**Помощники:** {helpers_str}\n\n"
            f"**Доказательства:** [Кликабельная ссылка]({self.proof_link.value})\n\n"
            f"📅 **Дата:** {datetime.now(msk_tz).strftime('%d.%m.%Y %H:%M')}"
        )
        
        embed = discord.Embed(title="📝 Отчет о проведении собеседования", description=desc, color=discord.Color.teal())
        
        if channel:
            await channel.send(embed=embed)
        
        self.parent_view.clear_items()
        await interaction.edit_original_response(content="✅ Отчет о собеседовании успешно отправлен!", view=self.parent_view)

class InterviewBuilderView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
        self.resp_select = discord.ui.UserSelect(placeholder="Кто проводил (Ответственный)", min_values=1, max_values=1, custom_id="int_resp_sel")
        self.resp_select.callback = self.select_defer
        
        self.help_select = discord.ui.UserSelect(placeholder="Кто оказывал помощь (можно не выбирать)", min_values=0, max_values=20, custom_id="int_help_sel")
        self.help_select.callback = self.select_defer
        
        self.add_item(self.resp_select)
        self.add_item(self.help_select)

    async def select_defer(self, interaction: discord.Interaction):
        await interaction.response.defer()

    @discord.ui.button(label="Продолжить", style=discord.ButtonStyle.green, row=2)
    async def submit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        resp_users = self.resp_select.values
        help_users = self.help_select.values

        if not resp_users:
            return await interaction.response.send_message("❌ Выберите ответственного сотрудника!", ephemeral=True)

        # Валидация ролей (Проверяем, есть ли у выбранных людей права на собеседования)
        all_users = list(resp_users) + list(help_users)
        for u in all_users:
            member = interaction.guild.get_member(u.id)
            if member and INTERVIEW_WORKER_ROLES:
                has_role = any(r.id in INTERVIEW_WORKER_ROLES for r in member.roles)
                if not has_role:
                    return await interaction.response.send_message(f"❌ Ошибка: У сотрудника {member.mention} нет роли для проведения собеседований!", ephemeral=True)

        # Открываем модальное окно для вставки ссылки
        await interaction.response.send_modal(InterviewProofModal(resp_users[0], help_users, self))

class InterviewSetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Подать отчет о собеседовании", style=discord.ButtonStyle.blurple, custom_id="setup_interview_btn", emoji="📝")
    async def interview_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Заполните форму для отчета:", view=InterviewBuilderView(), ephemeral=True)