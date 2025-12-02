import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv 
import time
import asyncio

# Tải biến môi trường (Chỉ dùng khi chạy cục bộ)
load_dotenv() 

# ====================================================================
# THIẾT LẬP (LẤY TỪ BIẾN MÔI TRƯỜNG)
# ====================================================================

TOKEN = os.getenv("DISCORD_TOKEN") 

try:
    FEEDBACK_CHANNEL_ID = int(os.getenv("FEEDBACK_CHANNEL_ID")) 
except (TypeError, ValueError):
    # Giá trị mặc định nếu biến môi trường bị thiếu
    FEEDBACK_CHANNEL_ID = 0 

# ====================================================================
# 1. LỚP VIEW XỬ LÝ LỰA CHỌN TRONG DM (ANON/PUBLIC)
# ====================================================================

class AnonChoiceView(discord.ui.View):
    def __init__(self, original_content, original_author_id, feedback_channel_id, bot_instance):
        super().__init__(timeout=180) 
        self.original_content = original_content
        self.original_author_id = original_author_id
        self.feedback_channel_id = feedback_channel_id
        self.bot = bot_instance
        self.message = None 

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(
                content="⚠️ **Lựa chọn phản hồi đã hết thời gian (3 phút).** Vui lòng gửi lại tin nhắn.", 
                embed=None, 
                view=self
            )

    async def send_feedback(self, interaction: discord.Interaction, is_anonymous: bool):
        feedback_channel = self.bot.get_channel(self.feedback_channel_id)
        
        new_footer_base = "Cảm ơn quý khách đã feedback, Naloria sẽ cố gắng hoàn thiện hơn trong tương lai ❤️"

        if is_anonymous:
            title = ":envelope_with_arrow: Phản hồi Ẩn danh Mới"
            footer_text = f"{new_footer_base} (Gửi Ẩn danh)"
            color = discord.Color.from_rgb(255, 99, 71)
        else:
            author = interaction.user
            # SỬ DỤNG MENTION TRONG TIÊU ĐỀ
            title = f":loudspeaker: Phản hồi CÔNG KHAI từ {author.mention}" 
            footer_text = f"{new_footer_base} (Gửi Công khai bởi {author} | ID: {author.id})"
            color = discord.Color.blue()
        
        embed_feedback = discord.Embed(
            title=title,
            description=self.original_content,
            color=color
        )
        embed_feedback.set_footer(text=footer_text)
        
        # 2. Gửi đến kênh Admin
        if feedback_channel:
            sent_message = await feedback_channel.send(embed=embed_feedback)
            await sent_message.add_reaction("✅")
        
        # 3. Vô hiệu hóa nút trong DM
        self.stop()
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=self)

        # 4. Gửi xác nhận cho người dùng
        confirmation_msg = f"✅ Phản hồi của bạn đã được gửi thành công! ({'Ẩn danh' if is_anonymous else 'Công khai'})"
        await interaction.response.send_message(embed=discord.Embed(title="Gửi Thành Công", description=confirmation_msg, color=discord.Color.green()), ephemeral=True)


    @discord.ui.button(label="Gửi Ẩn danh", style=discord.ButtonStyle.red, emoji="👤")
    async def anonymous_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.original_author_id:
            return await interaction.response.send_message("❌ Bạn không phải là người gửi tin nhắn này.", ephemeral=True)
        await self.send_feedback(interaction, is_anonymous=True)

    @discord.ui.button(label="Gửi Công khai", style=discord.ButtonStyle.green, emoji="✅")
    async def public_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.original_author_id:
            return await interaction.response.send_message("❌ Bạn không phải là người gửi tin nhắn này.", ephemeral=True)
        await self.send_feedback(interaction, is_anonymous=False)

# --------------------------------------------------------------------
# 2. LỚP VIEW CỐ ĐỊNH TRONG KÊNH (PERSISTENT VIEW)
# --------------------------------------------------------------------

class ChannelLauncherView(discord.ui.View):
    def __init__(self, bot_instance):
        super().__init__(timeout=None) 
        self.bot = bot_instance
        
    @discord.ui.button(label="Gửi Phản hồi/Góp ý", style=discord.ButtonStyle.primary, emoji="✍️", custom_id="persistent_feedback_button")
    async def launch_feedback_dm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Đã nhận được yêu cầu! Vui lòng kiểm tra Tin nhắn Trực tiếp (DM) để tiếp tục.",
            ephemeral=True
        )

        try:
            await interaction.user.send(
                "Chào bạn! Vui lòng **gõ và gửi nội dung phản hồi** của bạn vào kênh DM này. Sau đó, tôi sẽ hỏi bạn muốn gửi **Ẩn danh** hay **Công khai**."
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Lỗi: Tôi không thể gửi DM cho bạn. Vui lòng kiểm tra cài đặt quyền riêng tư.", 
                ephemeral=True
            )

# ====================================================================
# CẤU HÌNH BOT VÀ SỰ KIỆN READY
# ====================================================================

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.dm_messages = True
intents.members = True 

# Khởi tạo Bot
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print('----------------------------------------------------')
    print(f'Bot đã đăng nhập với tên: {bot.user}')
    
    try:
        # Đăng ký View cố định và đồng bộ lệnh slash
        bot.add_view(ChannelLauncherView(bot)) 
        
        synced = await bot.tree.sync()
        print(f"Đã đồng bộ hóa {len(synced)} lệnh slash.")
    except Exception as e:
        print(f"Lỗi khi đồng bộ hóa: {e}")
        
    print('----------------------------------------------------')

# ====================================================================
# LỆNH PREFIX CŨ: Thiết lập thông báo Phản hồi trong kênh
# ====================================================================

@bot.command(name='setup_feedback')
@commands.has_permissions(administrator=True)
async def setup_feedback(ctx):
    """Lệnh Admin: Gửi Embed thông báo phản hồi vào kênh."""
    
    if isinstance(ctx.channel, discord.DMChannel):
        return await ctx.send("Lệnh này chỉ có thể được sử dụng trong máy chủ (server).")

    embed = discord.Embed(
        title="📝 Kênh Phản hồi & Góp ý Chính thức 📝",
        description=(
            "Bạn có thể gửi phản hồi, báo lỗi, hoặc góp ý tính năng.\n\n"
            "**CÁCH SỬ DỤNG:**\n"
            "1. Nhấn nút **'Gửi Phản hồi/Góp ý'** bên dưới.\n"
            "2. Bot sẽ mở **Tin nhắn Trực tiếp (DM)** với bạn."
        ),
        color=discord.Color.gold()
    )
    embed.set_footer(text="Phản hồi của bạn sẽ được chuyển đến đội ngũ quản trị.")

    await ctx.send(embed=embed, view=ChannelLauncherView(bot))

    try:
        await ctx.message.delete()
    except:
        pass

# ====================================================================
# LỆNH 1 (SLASH): GỬI THÔNG BÁO @EVERYONE
# ====================================================================

@bot.tree.command(name='thong_bao_all', description='Gửi thông báo và ping @everyone trong kênh hiện tại.')
@app_commands.describe(
    noi_dung='Nội dung thông báo (Bot sẽ tự thêm @everyone).'
)
@app_commands.default_permissions(mention_everyone=True)
async def announce_everyone_slash(interaction: discord.Interaction, noi_dung: str):
    
    if not interaction.user.guild_permissions.mention_everyone:
        return await interaction.response.send_message("❌ Bạn không có quyền 'Gắn thẻ mọi người' (@everyone) để sử dụng lệnh này.", ephemeral=True)
    
    await interaction.response.defer(thinking=True, ephemeral=True)
    
    try:
        full_message = f"@everyone\n\n📢 **THÔNG BÁO TỪ ADMIN:**\n{noi_dung}"
        
        await interaction.channel.send(full_message)
        
        await interaction.followup.send("✅ Đã gửi thông báo @everyone thành công.", ephemeral=True)
        
    except discord.Forbidden:
        await interaction.followup.send("❌ Lỗi: Bot không có quyền 'Gắn thẻ mọi người' hoặc 'Gửi Tin nhắn' trong kênh này.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Đã xảy ra lỗi khi gửi thông báo: {e}", ephemeral=True)


# ====================================================================
# LỆNH 2 (SLASH): TẠO KÊNH THEO DANH SÁCH TÊN CỤ THỂ
# ====================================================================

@bot.tree.command(name='tao_ds_kenh', description='Tạo kênh văn bản dựa trên danh sách tên được ngăn cách bằng dấu phẩy.')
@app_commands.describe(
    danh_sach_ten='Danh sách tên kênh, ngăn cách bằng dấu phẩy (ví dụ: Kế hoạch,Thảo luận,Báo cáo).'
)
@app_commands.default_permissions(manage_channels=True)
async def create_channels_list_slash(interaction: discord.Interaction, danh_sach_ten: str):
    
    if not interaction.user.guild_permissions.manage_channels:
        return await interaction.response.send_message("❌ Bạn không có quyền 'Quản lý Kênh'.", ephemeral=True)
    
    await interaction.response.defer(thinking=True)

    guild = interaction.guild
    if guild is None:
        return await interaction.followup.send("Lệnh này chỉ dùng được trong máy chủ (server) Discord.")

    gioi_han_discord = 500
    guild = await bot.fetch_guild(guild.id)
    current_channels = len(guild.channels)
    
    ten_kenh_list = [
        ten.strip() 
        for ten in danh_sach_ten.split(',') 
        if ten.strip()
    ]
    
    so_luong_yeu_cau = len(ten_kenh_list)
    
    if not ten_kenh_list:
        return await interaction.followup.send("❌ Vui lòng cung cấp danh sách tên kênh được ngăn cách bằng dấu phẩy.")

    if current_channels + so_luong_yeu_cau > gioi_han_discord:
        await interaction.followup.send(f"⚠️ Giới hạn Discord là {gioi_han_discord} kênh. Một số kênh trong danh sách của bạn sẽ không được tạo.")
        ten_kenh_list = ten_kenh_list[:gioi_han_discord - current_channels]
        so_luong_tao = len(ten_kenh_list)
    else:
        so_luong_tao = so_luong_yeu_cau

    start_time = time.time()
    await interaction.followup.send(f"🚀 Bắt đầu tạo **{so_luong_tao}** kênh theo danh sách cung cấp...")
    
    channels_created = 0
    
    # --- LOGIC TẠO KÊNH ĐÃ KHÔI PHỤC ---
    for channel_name_raw in ten_kenh_list:
        channel_name = channel_name_raw 
        
        try:
            await guild.create_text_channel(name=channel_name)
            channels_created += 1
            
            if channels_created % 10 == 0:
                await interaction.followup.send(f"✅ Đã tạo {channels_created}/{so_luong_tao} kênh theo danh sách. Vẫn đang tiếp tục...")

        except discord.Forbidden:
            await interaction.followup.send("❌ Lỗi: Bot không có quyền 'Quản lý Kênh' hoặc vai trò của bot không đủ cao.")
            break
        except Exception as e:
            await interaction.followup.send(f"❌ Đã xảy ra lỗi chung khi tạo kênh {channel_name}: {e}")
            break
    # --- KẾT THÚC LOGIC TẠO KÊNH ---

    end_time = time.time()
    tong_thoi_gian = end_time - start_time
    
    await interaction.followup.send(f"🎉 **HOÀN TẤT TẠO KÊNH THEO DANH SÁCH!**")
    await interaction.followup.send(f"Đã tạo thành công **{channels_created}** kênh.")
    await interaction.followup.send(f"Tổng thời gian: **{tong_thoi_gian:.2f} giây** (hoặc khoảng **{tong_thoi_gian / 60:.2f} phút**)")


# ====================================================================
# SỰ KIỆN XỬ LÝ DM CHO PHẢN HỒI
# ====================================================================

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if isinstance(message.channel, discord.DMChannel):
        if len(message.content.strip()) < 5:
             await message.author.send("Tin nhắn quá ngắn để được coi là phản hồi. Vui lòng cung cấp nội dung chi tiết hơn.")
             return

        try:
            view = AnonChoiceView(
                original_content=message.content,
                original_author_id=message.author.id,
                feedback_channel_id=FEEDBACK_CHANNEL_ID,
                bot_instance=bot
            )

            preview_content = message.content[:50] + ("..." if len(message.content) > 50 else "")
            embed_choice = discord.Embed(
                title="❓ Lựa chọn Gửi Phản hồi",
                description=f"Bạn muốn gửi nội dung phản hồi này như thế nào? (Nội dung của bạn: **{preview_content}**)",
                color=discord.Color.gold()
            )
            embed_choice.set_footer(text="Nếu bạn không chọn trong 3 phút, tin nhắn sẽ bị hủy.")
            
            sent_message = await message.author.send(embed=embed_choice, view=view)
            view.message = sent_message
            
        except Exception as e:
            print(f"Lỗi khi xử lý DM và gửi lựa chọn: {e}")
            await message.author.send("❌ Đã xảy ra lỗi không xác định khi xử lý phản hồi của bạn.")

    await bot.process_commands(message)

# ====================================================================
# CHẠY BOT
# ====================================================================

if TOKEN:
    try:
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        print("LỖI: Token Discord không hợp lệ. Vui lòng kiểm tra lại biến môi trường DISCORD_TOKEN.")
    except Exception as e:
        print(f"Đã xảy ra lỗi khi chạy bot: {e}")
else:
    print("LỖI: Không tìm thấy Token. Vui lòng kiểm tra biến môi trường DISCORD_TOKEN.")