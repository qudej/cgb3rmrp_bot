import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

# Импортируем наши модули
from config import *
from utils import is_senior_staff, extract_user_data, apply_rank_roles, is_senior_dept_staff
from viewshr import RoleRequestView, AdminReviewView, AdminDismissalReviewView, ContextMenuDismissModal
from viewsdept import DepartmentSetupView, DepartmentReviewView
from viewspunish import PunishmentSetupView, PunishmentBuilderView
from viewssupply import SupplySetupView, SupplyRequestControlsView
from viewsranks import SetRankView
from viewsedu import InstructionSetupView, InstructionReviewView
from viewsreports import ReportSetupView, ReportReviewView, PromotionQueueView

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
        self.add_view(InstructionSetupView())
        self.add_view(InstructionReviewView())
        self.add_view(ReportSetupView())
        self.add_view(ReportReviewView())
        self.add_view(PromotionQueueView())
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
    if not is_senior_staff(interaction.user) and not is_senior_dept_staff(interaction.user):
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
    
    success = await apply_rank_roles(interaction.user, member, new_rank)
    if not success:
        return await interaction.followup.send("❌ Ошибка: Пользователь выше/равен вам по рангу, либо вы пытаетесь изменить ранг себе/владельцу.", ephemeral=True)

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

    target_channels = {
        HR_SETUP_CHANNEL_ID: {
            "title": "Кадровый аудит | ЦГБ №3",
            "desc": "Выберите нужный пункт меню ниже, чтобы подать заявку.",
            "color": discord.Color.dark_theme(),
            "view": RoleRequestView
        },
        PUNISHMENT_SETUP_CHANNEL_ID: {
            "title": "🔨 Управление взысканиями",
            "desc": "Нажмите на кнопку ниже, чтобы выдать дисциплинарное взыскание сотруднику.",
            "color": discord.Color.dark_red(),
            "view": PunishmentSetupView
        },
        SUPPLY_SETUP_CHANNEL_ID: {
            "title": "📦 Запрос поставок",
            "desc": "Нажмите на кнопку ниже, чтобы запросить поставку медикаментов (ЗМХ / МС).",
            "color": discord.Color.dark_blue(),
            "view": SupplySetupView
        },
        DEPT_SETUP_CHANNEL_ID: {
            "title": "🏥 Заявки в отделы",
            "desc": "Выберите отдел, в который хотите подать заявку:",
            "color": discord.Color.brand_green(),
            "view": DepartmentSetupView
        },
        INSTRUCTION_SETUP_CHANNEL_ID: {
            "title": "📚 Учебный центр",
            "desc": "Нажмите на кнопку ниже, чтобы запросить проведение инструктажа или экзамена.",
            "color": discord.Color.gold(),
            "view": InstructionSetupView
        }
    }

    for channel_id, data in target_channels.items():
        channel = bot.get_channel(channel_id)
        if not channel:
            continue
            
        async for msg in channel.history(limit=25):
            if msg.author == bot.user and msg.embeds and msg.embeds[0].title == data["title"]:
                try:
                    await msg.delete()
                except Exception:
                    pass
        
        embed = discord.Embed(title=data["title"], description=data["desc"], color=data["color"])
        try:
            new_msg = await channel.send(embed=embed, view=data["view"]())
            
            global sticky_message_ids
            sticky_message_ids[channel_id] = new_msg.id
        except Exception:
            pass

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

    # 5. Эмбед для отчетов на повышение
    report_channel = bot.get_channel(REPORT_SETUP_CHANNEL_ID)
    if report_channel:
        embed_rep = discord.Embed(
            title="📋 Отчеты на повышение",
            description="Выберите ваш отдел ниже, чтобы оставить отчет о проделанной работе.",
            color=discord.Color.purple()
        )
        await report_channel.send(embed=embed_rep, view=ReportSetupView())
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass

sticky_message_ids = {} # Хранит ID текущих липких сообщений (channel_id: message_id)
sticky_locks = {}       # Хранит блокировки (очередь) для каждого канала

@bot.event
async def on_message(message: discord.Message):
    await bot.process_commands(message)

    if message.content.startswith(BOT_PREFIX):
        return
    
    target_channels = {
        HR_SETUP_CHANNEL_ID: {
            "title": "Кадровый аудит | ЦГБ №3",
            "desc": "Выберите нужный пункт меню ниже, чтобы подать заявку.",
            "color": discord.Color.dark_theme(),
            "view": RoleRequestView
        },
        PUNISHMENT_SETUP_CHANNEL_ID: {
            "title": "🔨 Управление взысканиями",
            "desc": "Нажмите на кнопку ниже, чтобы выдать дисциплинарное взыскание сотруднику.",
            "color": discord.Color.dark_red(),
            "view": PunishmentSetupView
        },
        SUPPLY_SETUP_CHANNEL_ID: {
            "title": "📦 Запрос поставок",
            "desc": "Нажмите на кнопку ниже, чтобы запросить поставку медикаментов (ЗМХ / МС).",
            "color": discord.Color.dark_blue(),
            "view": SupplySetupView
        },
        DEPT_SETUP_CHANNEL_ID: {
            "title": "🏥 Заявки в отделы",
            "desc": "Выберите отдел, в который хотите подать заявку:",
            "color": discord.Color.brand_green(),
            "view": DepartmentSetupView
        },
        INSTRUCTION_SETUP_CHANNEL_ID: {
            "title": "📚 Учебный центр",
            "desc": "Нажмите на кнопку ниже, чтобы запросить проведение инструктажа или экзамена.",
            "color": discord.Color.gold(),
            "view": InstructionSetupView
        }
    }

    channel_id = message.channel.id
    if channel_id not in target_channels:
        return

    data = target_channels[channel_id]

    if message.author == bot.user and message.embeds and message.embeds[0].title == data["title"]:
        return

    if channel_id not in sticky_locks:
        sticky_locks[channel_id] = asyncio.Lock()

    async with sticky_locks[channel_id]:
        try:
            last_messages = [msg async for msg in message.channel.history(limit=1)]
            if last_messages:
                last_msg = last_messages[0]
                if last_msg.author == bot.user and last_msg.embeds and last_msg.embeds[0].title == data["title"]:
                    sticky_message_ids[channel_id] = last_msg.id
                    return
        except Exception:
            pass

        old_msg_id = sticky_message_ids.get(channel_id)
        if old_msg_id:
            try:
                old_msg = await message.channel.fetch_message(old_msg_id)
                await old_msg.delete()
            except discord.NotFound:
                pass # Сообщение уже было удалено
            except Exception:
                pass
        else:
            async for msg in message.channel.history(limit=30):
                if msg.author == bot.user and msg.embeds and msg.embeds[0].title == data["title"]:
                    try: 
                        await msg.delete()
                    except: 
                        pass

        embed = discord.Embed(title=data["title"], description=data["desc"], color=data["color"])
        new_msg = await message.channel.send(embed=embed, view=data["view"]())
        sticky_message_ids[channel_id] = new_msg.id




if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        print("❌ КРИТИЧЕСКАЯ ОШИБКА: Токен не найден! Проверьте файл .env")
    else:
        bot.run(DISCORD_BOT_TOKEN)