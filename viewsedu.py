import discord
from datetime import datetime
from config import *
from utils import is_senior_staff, extract_user_data

class InstructionReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not is_senior_staff(interaction.user):
            await interaction.response.send_message("❌ Это действие доступно только Старшему Составу.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Проведено", style=discord.ButtonStyle.green, custom_id="edu_confirm_btn")
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = interaction.message.embeds[0]
        
        _, admin_name, _ = extract_user_data(interaction.user)
        
        embed.title = "✅ Инструктаж проведен"
        embed.color = discord.Color.green()
        embed.description += f"\n\n**Кто провел:**\n{admin_name} ({interaction.user.mention})\n 📅{datetime.now(msk_tz).strftime('%d.%m.%Y %H:%M')}"
        
        self.clear_items()
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Отменить", style=discord.ButtonStyle.red, custom_id="edu_cancel_btn")
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = interaction.message.embeds[0]
        
        _, admin_name, _ = extract_user_data(interaction.user)
        
        embed.title = "❌ Инструктаж отменен"
        embed.color = discord.Color.red()
        embed.description += f"\n\n**Отменил:**\n{admin_name} ({interaction.user.mention})"
        
        self.clear_items()
        await interaction.message.edit(embed=embed, view=self)

class InstructionBuilderView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.selected_type = None
        self.selected_rank = None

        # 1. Выпадающий список инструктажей
        inst_options = [discord.SelectOption(label=inst) for inst in INSTRUCTION_TYPES[:25]]
        self.inst_select = discord.ui.Select(placeholder="Выберите нужный инструктаж...", min_values=1, max_values=1, options=inst_options)
        self.inst_select.callback = self.inst_callback
        self.add_item(self.inst_select)

        # 2. Выпадающий список рангов (Берем из RANK_SYSTEM автоматически)
        rank_options = [discord.SelectOption(label=f"[{r['rank_num']}] {r['name']}", value=r['name']) for r in RANK_SYSTEM[:25]]
        self.rank_select = discord.ui.Select(placeholder="Выберите вашу должность...", min_values=1, max_values=1, options=rank_options)
        self.rank_select.callback = self.rank_callback
        self.add_item(self.rank_select)

    async def inst_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.selected_type = self.inst_select.values[0]

    async def rank_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.selected_rank = self.rank_select.values[0]

    @discord.ui.button(label="Отправить запрос", style=discord.ButtonStyle.green, row=2)
    async def submit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_type or not self.selected_rank:
            return await interaction.response.send_message("❌ Выберите Инструктаж и Должность в списках выше!", ephemeral=True)

        # 1. Находим отдел пользователя
        current_dept = "О"
        for d_name, r_id in DEPARTMENTS_ROLES.items():
            if any(r.id == r_id for r in interaction.user.roles):
                current_dept = d_name
                if d_name != "О": break
                
        dept_full_names = {
            "О": "Ординатура", "АБ": "Администрация больницы",
            "БСМП": "Бригада скорой медицинской помощи", "КДО": "Консультативно-диагностическое отделение",
            "КУЦ": "Кадровый учебный центр"
        }
        full_dept = dept_full_names.get(current_dept, current_dept)

        # 2. Извлекаем красивое имя и статик из никнейма пользователя
        _, name, static = extract_user_data(interaction.user)

        # 3. Формируем эмбед по вашему шаблону
        desc = (
            f"📍 **Ваше ФИО**\n{interaction.user.mention}\n"
            f"🥼 **Ваша должность**\n{self.selected_rank}\n"
            f"💼 **Ваш отдел**\n{full_dept}\n"
            f"📚 **Ваш запрос**\n{self.selected_type}\n\n"
            f"📅 {datetime.now(msk_tz).strftime('%d.%m.%Y %H:%M')}"
        )
        
        embed = discord.Embed(title="⏳ Запрос инструктажа", description=desc, color=discord.Color.yellow())
        embed.set_footer(text=f"ID пользователя: {interaction.user.id}")

        # 4. Собираем пинги (Зав + Зам + Старший сотрудник этого отдела)
        ping_dept = "КУЦ" if current_dept == "О" else current_dept
        
        role_ids = DEPT_PING_ROLES.get(ping_dept, []).copy()
        senior_role = SENIOR_DEPT_ROLES.get(ping_dept)
        if senior_role:
            role_ids.append(senior_role)

        mentions_str = " ".join([f"<@&{r_id}>" for r_id in set(role_ids)])

        # 5. Отправляем
        channel = interaction.guild.get_channel(INSTRUCTION_REQUESTS_CHANNEL_ID)
        if channel:
            await channel.send(content=mentions_str, embed=embed, view=InstructionReviewView())

        # Удаляем списки с экрана и пишем "Успешно"
        self.clear_items()
        await interaction.response.edit_message(content=f"✅ Ваш запрос на **{self.selected_type}** успешно отправлен!", view=self)


class InstructionSetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Запросить инструктаж", style=discord.ButtonStyle.blurple, custom_id="setup_edu_btn", emoji="📚")
    async def req_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Заполните форму для запроса инструктажа:", view=InstructionBuilderView(), ephemeral=True)