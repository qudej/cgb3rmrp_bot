import discord
from datetime import datetime
from config import *
from utils import apply_rank_roles, extract_user_data, is_senior_staff

class SetRankSelect(discord.ui.Select):
    def __init__(self, target_member: discord.Member):
        options =[discord.SelectOption(label=f"[{r['rank_num']}] {r['name']}", value=str(i)) for i, r in enumerate(RANK_SYSTEM[:25])]
        super().__init__(placeholder="Выберите новый ранг...", options=options)
        self.target_member = target_member

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not is_senior_staff(interaction.user):
            return await interaction.followup.send("❌ Доступно только Старшему Составу.")
            
        new_rank_idx = int(self.values[0])
        new_rank = RANK_SYSTEM[new_rank_idx]
        
        success = await apply_rank_roles(self.target_member, new_rank)
        if not success:
            return await interaction.followup.send("❌ Нет прав для изменения ролей.")

        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="🏷️ Кадровый аудит: Изменение ранга",
                description=(f"👤 **Сотрудник:** {self.target_member.mention}\n"
                             f"📈 **Новый ранг:** **{new_rank['name']}**\n\n"
                             f"🤝 **Установил:** {interaction.user.mention}\n"
                             f"📅 **Дата:** {datetime.now(msk_tz).strftime('%d.%m.%Y %H:%M')}"),
                color=discord.Color.blue()
            )
            await log_channel.send(embed=log_embed)
        await interaction.followup.send(f"✅ Ранг сотрудника изменен на **{new_rank['name']}**", ephemeral=True)

class SetRankView(discord.ui.View):
    def __init__(self, target_member: discord.Member):
        super().__init__()
        self.add_item(SetRankSelect(target_member))