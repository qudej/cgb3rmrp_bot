import discord
from datetime import datetime
from config import *
from utils import is_senior_staff

async def send_supply_report(interaction: discord.Interaction, orig_msg: discord.Message, types_str: str, resp_user, help_users, status: str, details=None):
    channel = interaction.guild.get_channel(SUPPLY_REPORT_CHANNEL_ID)
    
    if help_users: helpers_str = ", ".join([u.mention for u in help_users])
    else: helpers_str = "Нет помощников"

    color = discord.Color.green()
    if status == "Выбили": color = discord.Color.red()
    elif status == "Частично успешно": color = discord.Color.orange()

    faction_str = "Не указана"
    if orig_msg.embeds:
        for line in orig_msg.embeds[0].description.split("\n"):
            if line.startswith("**Фракция:** "):
                faction_str = line.replace("**Фракция:** ", "").strip()
                break

    desc = (
        f"**Ответственный:** {resp_user.mention}\n"
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
    details = discord.ui.TextInput(label="Что выбили / Довезли / Заспавнили", style=discord.TextStyle.paragraph, required=True)

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
        embed.add_field(
            name="📋 Результат", 
            value=f"**Отказал:** {interaction.user.mention}\n**Причина:** {self.reason_field.value}", 
            inline=False
        )
        self.original_view.clear_items()
        await self.original_msg.edit(embed=embed, view=self.original_view)
        await interaction.followup.send("✅ Запрос на поставку успешно отклонен.", ephemeral=True)

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
        if not is_senior_staff(interaction.user):
            return await interaction.response.send_message("❌ Управлять поставками может только Старший Состав.", ephemeral=True)
        types_str = await self.get_types_str(interaction.message)
        await interaction.response.send_message("Сформируйте отчет:", view=ReportBuilderView("Успешно", interaction.message, types_str), ephemeral=True)

    @discord.ui.button(label="Частично успешно", style=discord.ButtonStyle.blurple, custom_id="sup_partial", row=0)
    async def btn_partial(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_senior_staff(interaction.user):
            return await interaction.response.send_message("❌ Управлять поставками может только Старший Состав.", ephemeral=True)
        types_str = await self.get_types_str(interaction.message)
        await interaction.response.send_message("Сформируйте отчет:", view=ReportBuilderView("Частично успешно", interaction.message, types_str), ephemeral=True)

    @discord.ui.button(label="Выбили", style=discord.ButtonStyle.red, custom_id="sup_fail", row=0)
    async def btn_fail(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_senior_staff(interaction.user):
            return await interaction.response.send_message("❌ Управлять поставками может только Старший Состав.", ephemeral=True)
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
        embed.add_field(name="📋 Результат", value=f"Отменил: {interaction.user.mention}", inline=False)
        self.clear_items()
        await interaction.message.edit(embed=embed, view=self)

class SupplyFactionModal(discord.ui.Modal, title="Укажите фракцию"):
    faction_field = discord.ui.TextInput(label="Название фракции", placeholder="Например: FIB / LSPD / Правительство", required=True)

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
        await interaction.response.send_modal(SupplyFactionModal(self))

class SupplySetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Запросить поставку", style=discord.ButtonStyle.blurple, custom_id="setup_supply_btn", emoji="📦")
    async def supply_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Заполните форму для запроса:", view=SupplyBuilderView(), ephemeral=True)