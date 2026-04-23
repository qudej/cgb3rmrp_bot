import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

# Импортируем наши модули
from config import *
from utils import is_senior_staff, extract_user_data, apply_rank_roles
from viewshr import RoleRequestView, AdminReviewView, AdminDismissalReviewView, ContextMenuDismissModal
from viewsdept import DepartmentSetupView, DepartmentReviewView
from viewspunish import PunishmentSetupView, PunishmentBuilderView
from viewssupply import SupplySetupView, SupplyRequestControlsView
from viewsranks import SetRankView

class MyBot(commands.Bot):
    async def setup_hook(self):
        # Регистрируем все вечные кнопки из разных модулей
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

# === КОНТЕКСТНЫЕ МЕНЮ (ПКМ ПО ПОЛЬЗОВАТЕЛЮ) ===

@bot.tree.context_menu(name="Уволить")
async def context_dismiss_user(interaction: discord.Interaction, member: discord.Member):
    if not is_senior_staff(interaction.user):
        return await interaction.response.send_message("❌ У вас нет прав. Доступно только Старшему Составу.", ephemeral=True)
    await interaction.response.send_modal(ContextMenuDismissModal(member))

@bot.tree.context_menu(name="Выдать взыскание")
async def context_punishment(interaction: discord.Interaction, member: discord.Member):
    if not is_senior_staff(interaction.user):
        return await interaction.response.send_message("❌ Доступно только Старшему Составу.", ephemeral=True)
    await interaction.response.send_message(f"Выдача взыскания для {member.mention}:", view=PunishmentBuilderView(target_member=member), ephemeral=True)

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

# === ЗАПУСК И КОМАНДЫ ===

@bot.event
async def on_ready():
    print(f"Бот {bot.user} успешно запущен и синхронизирован!")

@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def setup_command(ctx):
    # 1. Основной эмбед
    embed_hr = discord.Embed(title="Кадровый аудит | ЦГБ №3", description="Выберите нужный пункт меню ниже, чтобы подать заявку.", color=discord.Color.dark_theme())
    await ctx.send(embed=embed_hr, view=RoleRequestView())

    # 2. Эмбед для Взысканий
    punish_channel = bot.get_channel(PUNISHMENT_SETUP_CHANNEL_ID)
    if punish_channel:
        embed_punish = discord.Embed(title="🔨 Управление взысканиями", description="Нажмите на кнопку ниже, чтобы выдать дисциплинарное взыскание сотруднику.", color=discord.Color.dark_red())
        await punish_channel.send(embed=embed_punish, view=PunishmentSetupView())

    # 3. Эмбед для Поставок
    supply_channel = bot.get_channel(SUPPLY_SETUP_CHANNEL_ID)
    if supply_channel:
        embed_supply = discord.Embed(title="📦 Запрос поставок", description="Нажмите на кнопку ниже, чтобы запросить поставку медикаментов (ЗМХ / МС).", color=discord.Color.dark_blue())
        await supply_channel.send(embed=embed_supply, view=SupplySetupView())

    # 4. Эмбед для заявок в Отделы
    dept_channel = bot.get_channel(DEPT_SETUP_CHANNEL_ID)
    if dept_channel:
        embed_dept = discord.Embed(title="🏥 Заявки в отделы", description="Выберите отдел, в который хотите подать заявку:", color=discord.Color.brand_green())
        await dept_channel.send(embed=embed_dept, view=DepartmentSetupView())

    await ctx.message.delete()

if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        print("❌ КРИТИЧЕСКАЯ ОШИБКА: Токен не найден! Проверьте файл .env")
    else:
        bot.run(DISCORD_BOT_TOKEN)