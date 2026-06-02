import discord
import re
from datetime import datetime
from config import *
from utils import is_senior_staff, extract_user_data, apply_rank_roles


# СТАДИЯ 2: ОЧЕРЕДЬ НА ПОВЫШЕНИЕ (СТАРШИЙ СОСТАВ)
class PromotionQueueView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not is_senior_staff(interaction.user):
            await interaction.response.send_message("❌ Только Старший Состав может выдавать повышения.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Повысить", style=discord.ButtonStyle.green, custom_id="prom_queue_accept")
    async def btn_promote(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = interaction.message.embeds[0]
        
        # Читаем данные из подвала эмбеда
        try:
            footer_text = embed.footer.text
            match = re.search(r"ID: (\d+) \| Ранг: (\d+)", footer_text)
            user_id = int(match.group(1))
            current_rank_idx = int(match.group(2))
        except:
            return await interaction.followup.send("❌ Ошибка чтения данных.", ephemeral=True)

        member = interaction.guild.get_member(user_id)
        if not member:
            return await interaction.followup.send("❌ Сотрудник покинул сервер.", ephemeral=True)

        # Получаем старый и новый ранги
        old_rank = RANK_SYSTEM[current_rank_idx]
        new_rank = RANK_SYSTEM[current_rank_idx + 1]
        
        # Повышаем (снимаем старые роли, выдаем новые)
        success = await apply_rank_roles(interaction.user, member, new_rank)
        if not success:
            return await interaction.followup.send("❌ Ошибка иерархии: нет прав повысить этого сотрудника.", ephemeral=True)

        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            
            _, name, static = extract_user_data(member)
            log_embed = discord.Embed(
                title="🏷️ Кадровый аудит: Повышение",
                description=(
                    f"👤 **Сотрудник:** {member.mention} | {name} | {static}\n"
                    f"📈 **Повышение:** {old_rank['name']} ➔ **{new_rank['name']}**\n\n"
                    f"🤝 **Повысил:** {interaction.user.mention}\n"
                    f"📅 **Дата:** {datetime.now(msk_tz).strftime('%d.%m.%Y %H:%M')}"
                ),
                color=discord.Color.blue()
            )
            await log_channel.send(embed=log_embed)

        embed.title = "✅ Сотрудник повышен"
        embed.color = discord.Color.green()
        embed.add_field(name="📋 Результат", value=f"Повысил: {interaction.user.mention}", inline=False)
        self.clear_items()
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.red, custom_id="prom_queue_reject")
    async def btn_reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = interaction.message.embeds[0]
        embed.title = "❌ В повышении отказано"
        embed.color = discord.Color.red()
        embed.add_field(name="📋 Результат", value=f"Отклонил: {interaction.user.mention}", inline=False)
        self.clear_items()
        await interaction.message.edit(embed=embed, view=self)

# СТАДИЯ 1: ПРОВЕРКА ОТЧЕТОВ ОТДЕЛАМИ
class ReportReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def has_dept_perm(self, member: discord.Member, dept_name: str) -> bool:
        if member.guild_permissions.administrator: return True
        
        check_dept = "КУЦ" if dept_name == "О" else dept_name
        allowed_roles = DEPT_PING_ROLES.get(check_dept, [])
        return any(r.id in allowed_roles for r in member.roles)

    @discord.ui.button(label="Принять", style=discord.ButtonStyle.green, custom_id="rep_accept_btn")
    async def btn_accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = interaction.message.embeds[0]
        
        try:
            footer_text = embed.footer.text
            match = re.search(r"ID: (\d+) \| Отдел: (.*?) \| Ранг: (\d+)", footer_text)
            user_id = int(match.group(1))
            dept_name = match.group(2).strip()
            rank_idx = int(match.group(3))
        except:
            return await interaction.response.send_message("❌ Ошибка чтения данных.", ephemeral=True)

        if not self.has_dept_perm(interaction.user, dept_name) and not is_senior_staff(interaction.user):
            return await interaction.response.send_message("❌ У вас нет прав проверять отчеты этого отдела.", ephemeral=True)

        await interaction.response.defer()
        member = interaction.guild.get_member(user_id)
        if not member:
            return await interaction.followup.send("❌ Пользователь не найден.", ephemeral=True)

        # Меняем эмбед отчета на Одобренный
        embed.title = "✅ Отчет одобрен"
        embed.color = discord.Color.green()
        embed.add_field(name="📋 Проверил", value=interaction.user.mention, inline=False)
        self.clear_items()
        await interaction.message.edit(embed=embed, view=self)

        # === ФОРМИРУЕМ ЗАЯВКУ ДЛЯ СТАРШЕГО СОСТАВА (В ОЧЕРЕДЬ НУЖНОГО ОТДЕЛА) ===
        queue_channel_id = PROMOTION_QUEUE_CHANNELS.get(dept_name)
        queue_channel = interaction.guild.get_channel(queue_channel_id) if queue_channel_id else None
        
        if queue_channel:
            mention_str, name, static = extract_user_data(member)
            formatted_user = member.display_name if member else f"{name} | {static}"
            
            old_rank_name = RANK_SYSTEM[rank_idx]["name"]
            new_rank_name = RANK_SYSTEM[rank_idx + 1]["name"]
            
            desc = (
                f"**Кандидат:** {mention_str}\n"
                f"**Отдел:** {dept_name}\n"
                f"**Ссылка на отчет:** [Перейти к отчету]({interaction.message.jump_url})\n"
                f"**Повышение:** {old_rank_name} ➔ **{new_rank_name}**"
            )
            
            queue_embed = discord.Embed(title="📈 Очередь на повышение", description=desc, color=discord.Color.blue())
            queue_embed.set_footer(text=f"ID: {user_id} | Ранг: {rank_idx}")
            
            await queue_channel.send(embed=queue_embed, view=PromotionQueueView())
        else:
            await interaction.followup.send(f"⚠️ Отчет одобрен, но канал очереди для повышения (отдел {dept_name}) не настроен!", ephemeral=True)

    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.red, custom_id="rep_reject_btn")
    async def btn_reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = interaction.message.embeds[0]
        # Простая проверка через чтение отдела из подвала
        try: dept_name = re.search(r"Отдел: (.*?) \|", embed.footer.text).group(1).strip()
        except: dept_name = ""

        if not self.has_dept_perm(interaction.user, dept_name) and not is_senior_staff(interaction.user):
            return await interaction.response.send_message("❌ У вас нет прав.", ephemeral=True)

        await interaction.response.defer()
        embed.title = "❌ Отчет отклонен"
        embed.color = discord.Color.red()
        embed.add_field(name="📋 Проверил", value=interaction.user.mention, inline=False)
        self.clear_items()
        await interaction.message.edit(embed=embed, view=self)


# ФОРМЫ ЗАПОЛНЕНИЯ ДЛЯ ИГРОКОВ
class ReportModal(discord.ui.Modal):
    # Добавлен параметр max_length=1000 для защиты от переполнения
    req_field = discord.ui.TextInput(
        label="Обязательные условия", 
        style=discord.TextStyle.paragraph, 
        placeholder="Ссылки на https://cgb3.pics/", 
        required=True,
        max_length=1000
    )
    extra_field = discord.ui.TextInput(
        label="Дополнительные баллы", 
        style=discord.TextStyle.paragraph, 
        placeholder="Если нет - напишите '-'", 
        required=True,
        max_length=1000
    )

    def __init__(self, dept_name: str, rank_idx: int):
        super().__init__(title=f"Отчет ({dept_name})")
        self.dept_name = dept_name
        self.rank_idx = rank_idx

    async def on_submit(self, interaction: discord.Interaction):
        channel_id = REPORT_REQUESTS_CHANNELS.get(self.dept_name)
        channel = interaction.guild.get_channel(channel_id) if channel_id else None
        
        if not channel:
            return await interaction.response.send_message(f"❌ Ошибка: Канал для отчетов отдела {self.dept_name} не настроен!", ephemeral=True)

        current_rank_name = RANK_SYSTEM[self.rank_idx]["name"]
        
        embed = discord.Embed(title=f"⏳ Отчет на повышение | {self.dept_name}", color=discord.Color.yellow())
        embed.add_field(name="Сотрудник", value=interaction.user.mention, inline=False)
        embed.add_field(name="Текущий ранг", value=current_rank_name, inline=False)
        
        # На всякий случай дополнительно обрезаем текст до 1024 символов при отправке
        embed.add_field(name="Обязательные условия", value=self.req_field.value[:1024], inline=False)
        embed.add_field(name="Дополнительные баллы", value=self.extra_field.value[:1024], inline=False)
        
        # Подвал (очень важно для кнопок)
        embed.set_footer(text=f"ID: {interaction.user.id} | Отдел: {self.dept_name} | Ранг: {self.rank_idx}")

        # Тегаем руководство отдела
        if self.dept_name == "О":
            # Для Ординатуры тегаем только одну общую роль КУЦ
            role_ids = [KUC_GENERAL_PING_ROLE_ID]
        else:
            # Для остальных отделов берем из словаря Зав/Зам
            role_ids = DEPT_PING_ROLES.get(self.dept_name, [])
            
        mentions_str = " ".join([f"<@&{r_id}>" for r_id in role_ids])

        await channel.send(content=mentions_str, embed=embed, view=ReportReviewView())
        await interaction.response.send_message("✅ Ваш отчет успешно отправлен на проверку!", ephemeral=True)

class ReportRankSelectView(discord.ui.View):
    def __init__(self, dept_name: str):
        super().__init__(timeout=None)
        self.dept_name = dept_name
        self.selected_rank_idx = None

        # Создаем опции только для тех рангов, с которых МОЖНО повыситься (убираем самый последний)
        options =[discord.SelectOption(label=f"[{r['rank_num']}] {r['name']}", value=str(i)) for i, r in enumerate(RANK_SYSTEM[:-1])]
        self.rank_select = discord.ui.Select(placeholder="Выберите ваш ТЕКУЩИЙ ранг...", options=options)
        self.rank_select.callback = self.rank_callback
        self.add_item(self.rank_select)

    async def rank_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.selected_rank_idx = int(self.rank_select.values[0])

    @discord.ui.button(label="Продолжить", style=discord.ButtonStyle.green, row=1)
    async def submit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.selected_rank_idx is None:
            return await interaction.response.send_message("❌ Выберите ваш ранг из списка!", ephemeral=True)
        # Открываем форму
        await interaction.response.send_modal(ReportModal(self.dept_name, self.selected_rank_idx))

# ГЛАВНОЕ МЕНЮ ОТЧЕТОВ
class ReportSetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ординатура", style=discord.ButtonStyle.gray, custom_id="report_dept_o")
    async def o_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(view=ReportRankSelectView("О"), ephemeral=True)

    @discord.ui.button(label="БСМП", style=discord.ButtonStyle.blurple, custom_id="report_dept_bsmp")
    async def bsmp_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(view=ReportRankSelectView("БСМП"), ephemeral=True)

    @discord.ui.button(label="АБ", style=discord.ButtonStyle.blurple, custom_id="report_dept_ab")
    async def ab_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(view=ReportRankSelectView("АБ"), ephemeral=True)

    @discord.ui.button(label="КУЦ", style=discord.ButtonStyle.blurple, custom_id="report_dept_kuc")
    async def kuc_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(view=ReportRankSelectView("КУЦ"), ephemeral=True)

    @discord.ui.button(label="КДО", style=discord.ButtonStyle.blurple, custom_id="report_dept_kdo")
    async def kdo_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(view=ReportRankSelectView("КДО"), ephemeral=True)