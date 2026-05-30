import discord
import re
from config import *
from utils import is_senior_staff, extract_user_data, can_target_member

class DepartmentReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    # Локальная функция проверки прав (является ли человек руководством конкретного отдела)
    def has_dept_perm(self, member: discord.Member, dept_name: str) -> bool:
        if member.guild_permissions.administrator: return True
        allowed_roles = DEPT_PING_ROLES.get(dept_name, [])
        return any(r.id in allowed_roles for r in member.roles)

    @discord.ui.button(label="Одобрить", style=discord.ButtonStyle.green, custom_id="dept_accept_btn")
    async def accept_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = interaction.message.embeds[0]
        
        # Считываем данные из подвала (footer)
        footer_text = embed.footer.text if embed.footer else ""
        try:
            match = re.search(r"ID: (\d+) \| (.*?) -> (.*)", footer_text)
            user_id = int(match.group(1))
            source_dept = match.group(2).strip()
            target_dept = match.group(3).strip()
        except:
            return await interaction.followup.send("❌ Не удалось прочитать системные данные заявки.", ephemeral=True)

        is_transfer = (source_dept != "О")

        # Проверяем права нажимающего
        has_source = self.has_dept_perm(interaction.user, source_dept)
        has_target = self.has_dept_perm(interaction.user, target_dept)

        if not has_source and not has_target:
            return await interaction.followup.send("❌ У вас нет прав одобрять заявки для этих отделов.", ephemeral=True)

        # Обработка двойного подтверждения для ПЕРЕВОДА
        if is_transfer:
            approved_something = False
            for i, field in enumerate(embed.fields):
                # Если админ из старого отдела одобряет
                if field.name == f"Одобрение ({source_dept})" and has_source and "⏳" in field.value:
                    embed.set_field_at(i, name=field.name, value=f"✅ Одобрил: {interaction.user.mention}", inline=True)
                    approved_something = True
                # Если админ из нового отдела одобряет
                elif field.name == f"Одобрение ({target_dept})" and has_target and "⏳" in field.value:
                    embed.set_field_at(i, name=field.name, value=f"✅ Одобрил: {interaction.user.mention}", inline=True)
                    approved_something = True
            
            if not approved_something:
                return await interaction.followup.send("❌ Вы уже одобрили свою часть, либо у вас нет прав на оставшийся отдел.", ephemeral=True)

            # Проверяем, получены ли ОБА одобрения
            all_approved = True
            for field in embed.fields:
                if field.name.startswith("Одобрение") and "⏳" in field.value:
                    all_approved = False
                    break
            
            # Если второго одобрения еще нет - сохраняем и ждем
            if not all_approved:
                await interaction.message.edit(embed=embed, view=self)
                return await interaction.followup.send(f"✅ Вы одобрили перевод со своей стороны. Ожидаем решения от второго отдела.", ephemeral=True)

        # Обработка ВСТУПЛЕНИЯ (обычное)
        else:
            if not has_target:
                return await interaction.followup.send("❌ У вас нет прав принимать в этот отдел.", ephemeral=True)

        member = interaction.guild.get_member(user_id)
        if member:
            _, name, static = extract_user_data(member)
            new_nick = f"{target_dept} | {name} | {static}"
            try: await member.edit(nick=new_nick[:32])
            except discord.Forbidden: pass

            roles_to_remove = []
            for d, r_id in DEPARTMENTS_ROLES.items():
                r = interaction.guild.get_role(r_id)
                if r and r in member.roles: roles_to_remove.append(r)
                    
            for d, r_id in SENIOR_DEPT_ROLES.items():
                r = interaction.guild.get_role(r_id)
                if r and r in member.roles: roles_to_remove.append(r)

            roles_to_add = []
            role_to_add = interaction.guild.get_role(DEPARTMENTS_ROLES.get(target_dept, 0))
            if role_to_add: roles_to_add.append(role_to_add)

            user_roles_ids = [r.id for r in member.roles]
            is_senior = False
            for rank_data in RANK_SYSTEM:
                if rank_data["main_role"] in user_roles_ids and rank_data.get("is_senior", False):
                    is_senior = True
                    break
            
            if is_senior:
                new_senior_role = interaction.guild.get_role(SENIOR_DEPT_ROLES.get(target_dept, 0))
                if new_senior_role: roles_to_add.append(new_senior_role)

            try:
                if roles_to_remove: await member.remove_roles(*roles_to_remove)
                if roles_to_add: await member.add_roles(*roles_to_add)
            except discord.Forbidden: pass

        embed.title = embed.title.replace("⏳", "✅").replace("на рассмотрении", "одобрена")
        embed.color = discord.Color.green()
        
        if not is_transfer:
            embed.add_field(name="📋 Результат", value=f"Одобрил: {interaction.user.mention}", inline=False)
        else:
            embed.add_field(name="📋 Результат", value=f"Перевод полностью одобрен и завершен.", inline=False)

        self.clear_items()
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.red, custom_id="dept_reject_btn")
    async def reject_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = interaction.message.embeds[0]
        
        # Считываем данные из подвала
        footer_text = embed.footer.text if embed.footer else ""
        try:
            match = re.search(r"ID: (\d+) \| (.*?) -> (.*)", footer_text)
            source_dept = match.group(2).strip()
            target_dept = match.group(3).strip()
        except:
            return await interaction.followup.send("❌ Не удалось прочитать данные.", ephemeral=True)

        has_source = self.has_dept_perm(interaction.user, source_dept)
        has_target = self.has_dept_perm(interaction.user, target_dept)

        if not has_source and not has_target:
            return await interaction.followup.send("❌ У вас нет прав отклонять заявки для этих отделов.", ephemeral=True)

        embed.title = embed.title.replace("⏳", "❌").replace("на рассмотрении", "отклонена")
        embed.color = discord.Color.red()
        embed.add_field(name="📋 Результат", value=f"Отклонил: {interaction.user.mention}", inline=False)
        self.clear_items()
        await interaction.message.edit(embed=embed, view=self)

class DepartmentModal(discord.ui.Modal):
    rank_field = discord.ui.TextInput(label='Текущая должность', required=True)
    doc_field = discord.ui.TextInput(label='Удостоверение (ссылка)', placeholder='Ссылка на скриншот (imgur/yapx)', required=True)

    def __init__(self, dept_name: str):
        super().__init__(title=f'Заявка в {dept_name}')
        self.dept_name = dept_name

    async def on_submit(self, interaction: discord.Interaction):
        current_dept = "О" 
        for d_name, r_id in DEPARTMENTS_ROLES.items():
            if any(r.id == r_id for r in interaction.user.roles):
                current_dept = d_name
                if d_name != "О": break
        
        if current_dept == self.dept_name:
            return await interaction.response.send_message(f"❌ Вы уже состоите в отделе {self.dept_name}!", ephemeral=True)

        is_transfer = (current_dept != "О")
        req_type = "Перевод" if is_transfer else "Вступление"

        # Направляем в нужный канал
        if is_transfer:
            channel_id = TRANSFER_REQUESTS_CHANNEL_ID
        else:
            channel_id = DEPT_REQUESTS_CHANNELS.get(self.dept_name)
            
        channel = interaction.guild.get_channel(channel_id) if channel_id else None
        if not channel:
            return await interaction.response.send_message(f"❌ Ошибка: Канал для заявок не настроен!", ephemeral=True)
        
        dept_full_names = {
            "О": "Ординатура",
            "АБ": "Администрация больницы",
            "БСМП": "Бригада скорой медицинской помощи",
            "КДО": "Консультативно-диагностическое отделение",
            "КУЦ": "Кадровый учебный центр"
        }
        full_current = dept_full_names.get(current_dept, current_dept)
        full_target = dept_full_names.get(self.dept_name, self.dept_name)

        embed = discord.Embed(title=f"⏳ Заявка в отдел: {self.dept_name} на рассмотрении", color=discord.Color.yellow())
        embed.add_field(name="Кто подал", value=interaction.user.mention, inline=False)
        embed.add_field(name="Тип заявки", value=f"**{req_type}**\nИз: *{full_current}*\nВ: *{full_target}*", inline=False)
        embed.add_field(name="Должность", value=self.rank_field.value, inline=False)
        embed.add_field(name="Удостоверение", value=self.doc_field.value, inline=False)
        
        # Специальный подвал, по которому кнопки понимают, чья это заявка и откуда куда
        embed.set_footer(text=f"ID: {interaction.user.id} | {current_dept} -> {self.dept_name}")
        
        mentions = []
        if is_transfer:
            # Если перевод, создаем поля ожидания и пингуем ОБА отдела
            embed.add_field(name=f"Одобрение ({current_dept})", value="⏳ Ожидается", inline=True)
            embed.add_field(name=f"Одобрение ({self.dept_name})", value="⏳ Ожидается", inline=True)
            
            roles_src = DEPT_PING_ROLES.get(current_dept, [])
            roles_tgt = DEPT_PING_ROLES.get(self.dept_name, [])
            # set() уберет дубликаты, если вдруг человек пингуется дважды
            mentions = [f"<@&{r_id}>" for r_id in set(roles_src + roles_tgt)]
        else:
            roles_tgt = DEPT_PING_ROLES.get(self.dept_name, [])
            mentions = [f"<@&{r_id}>" for r_id in set(roles_tgt)]
        
        mentions_str = " ".join(mentions)
        await channel.send(content=mentions_str, embed=embed, view=DepartmentReviewView())
        await interaction.response.send_message(f"Ваша заявка на {req_type.lower()} в **{full_target}** успешно отправлена!", ephemeral=True)

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

    @discord.ui.button(label="КДО", style=discord.ButtonStyle.blurple, custom_id="setup_dept_kdo")
    async def kdo_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DepartmentModal("КДО"))