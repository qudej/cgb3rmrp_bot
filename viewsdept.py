import discord
from config import *
from utils import is_senior_staff, extract_user_data

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

            user_roles_ids =[r.id for r in member.roles]
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
        embed.add_field(name="📋 Результат", value=f"Одобрил: {interaction.user.mention}", inline=False)
        self.clear_items()
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.red, custom_id="dept_reject_btn")
    async def reject_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = interaction.message.embeds[0]
        embed.title = embed.title.replace("⏳", "❌").replace("на рассмотрении", "отклонена")
        embed.color = discord.Color.red()
        embed.add_field(name="📋 Результат", value=f"Отклонил: {interaction.user.mention}", inline=False)
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