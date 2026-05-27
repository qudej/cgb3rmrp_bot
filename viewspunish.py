import discord
from datetime import datetime
from config import *
from utils import is_senior_staff, is_senior_dept_staff, extract_user_data

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
        
        role_to_add_id = self.role_id
        final_role_name = self.role_name
        roles_to_remove_ids = set()
        
        user_role_ids = [r.id for r in self.target_member.roles]

        if role_to_add_id == PUNISHMENT_W1_ID:
            if PUNISHMENT_R1_ID in user_role_ids and PUNISHMENT_W2_ID in user_role_ids:
                role_to_add_id = PUNISHMENT_R2_ID
                final_role_name = "Выговор 2/2 (Авто-замена)"
                roles_to_remove_ids.update([PUNISHMENT_R1_ID, PUNISHMENT_W1_ID, PUNISHMENT_W2_ID])
                
            elif PUNISHMENT_W2_ID in user_role_ids:
                role_to_add_id = PUNISHMENT_R1_ID
                final_role_name = "Выговор 1/2 (Авто-замена 3 предов)"
                roles_to_remove_ids.update([PUNISHMENT_W1_ID, PUNISHMENT_W2_ID])
                
            elif PUNISHMENT_W1_ID in user_role_ids:
                role_to_add_id = PUNISHMENT_W2_ID
                final_role_name = "Предупреждение 2/3 (Авто-замена)"
                roles_to_remove_ids.add(PUNISHMENT_W1_ID)

        elif role_to_add_id == PUNISHMENT_W2_ID:
            roles_to_remove_ids.add(PUNISHMENT_W1_ID)
            
        elif role_to_add_id == PUNISHMENT_R1_ID:
            roles_to_remove_ids.update([PUNISHMENT_W1_ID, PUNISHMENT_W2_ID])
            
        elif role_to_add_id == PUNISHMENT_R2_ID:
            roles_to_remove_ids.update([PUNISHMENT_R1_ID, PUNISHMENT_W1_ID, PUNISHMENT_W2_ID])

        if roles_to_remove_ids:
            roles_to_remove = [guild.get_role(r_id) for r_id in roles_to_remove_ids if guild.get_role(r_id)]
            roles_to_remove = [r for r in roles_to_remove if r in self.target_member.roles]
            if roles_to_remove:
                try: await self.target_member.remove_roles(*roles_to_remove)
                except discord.Forbidden: pass

        role = guild.get_role(role_to_add_id)
        if role:
            try: await self.target_member.add_roles(role)
            except discord.Forbidden: 
                return await interaction.followup.send("❌ Нет прав на выдачу этой роли.", ephemeral=True)

        log_channel = guild.get_channel(PUNISHMENT_LOG_CHANNEL_ID)
        if log_channel:
            admin_mention, admin_name, admin_static = extract_user_data(interaction.user)
            target_mention, target_name, target_static = extract_user_data(self.target_member)
            
            embed = discord.Embed(title="🔨 Дисциплинарное взыскание", color=discord.Color.dark_orange())
            embed.description = (
                f"**Кто выдал:** {admin_mention}\n"
                f"**Кому:** {target_mention}\n"
                f"**Взыскание:** {role.mention if role else final_role_name}\n"
                f"**Причина:** {self.reason_field.value}\n\n"
                f"📅 **Дата:** {datetime.now(msk_tz).strftime('%d.%m.%Y %H:%M')}"
            )
            await log_channel.send(embed=embed)
            
        await interaction.followup.send(f"✅ Взыскание ({final_role_name}) успешно выдано {self.target_member.mention}.", ephemeral=True)

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
        if not is_senior_staff(interaction.user) and not is_senior_dept_staff(interaction.user):
            return await interaction.response.send_message("❌ Доступно только Старшему Составу.", ephemeral=True)
        await interaction.response.send_message("Заполните форму ниже:", view=PunishmentBuilderView(), ephemeral=True)