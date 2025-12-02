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
intents.members = True # BẮT BUỘC cho việc tag tên người dùng

# Khởi tạo Bot
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print('----------------------------------------------------')
    print(f'Bot đã đăng nhập với tên: {bot.user}')
    
    try:
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
    
    # CHECK BẢO VỆ LỖI CRASH
    if interaction.guild is None or interaction.user is None:
        return await interaction.response.send_message("❌ Lệnh này chỉ dùng được trong máy chủ (server).", ephemeral=True)
    
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
# LỆNH 2 (SLASH): TẠO KÊNH HÀNG LOẠT (Tên mẫu và số lượng 200)
# ====================================================================

@bot.tree.command(name="tao_hang_loat_kenh", description="Xóa TẤT CẢ kênh hiện có và tạo các kênh mới theo tên mẫu.")
@app_commands.describe(
    ten_mau="Tên mẫu cho kênh (ví dụ: 'kenh-thửnghiệm-' - Sẽ tự động thêm số thứ tự)",
    so_luong="Số lượng kênh bạn muốn tạo (tối đa 200 kênh)",
    xoa_kenh_hien_tai="XÁC NHẬN: Xóa TẤT CẢ các kênh (TRỪ kênh này) trước khi tạo kênh mới. (True/False)",
    thong_diep="Thông điệp tùy chỉnh để gửi vào kênh mới (sẽ kèm @everyone). (Tùy chọn)",
    url_anh_chao="URL ảnh (link trực tiếp) để thêm vào thông báo chào mừng kênh. (Tùy chọn)"
)
@app_commands.default_permissions(manage_channels=True)
async def tao_hang_loat_kenh_command(interaction: discord.Interaction, ten_mau: str, so_luong: app_commands.Range[int, 1, 200], xoa_kenh_hien_tai: bool, thong_diep: str = None, url_anh_chao: str = None):
    
    # CHECK BẢO VỆ LỖI CRASH
    if interaction.guild is None or interaction.user is None:
        return await interaction.response.send_message("❌ Lệnh này chỉ dùng được trong máy chủ (server).", ephemeral=True)
    
    if not interaction.user.guild_permissions.manage_channels:
        return await interaction.response.send_message("❌ Bạn không có quyền 'Quản lý Kênh'.", ephemeral=True)
    
    await interaction.response.defer(thinking=True) 
    
    guild = interaction.guild

    # =======================================================
    # BƯỚC XÓA KÊNH TRƯỚC (NẾU ĐƯỢC XÁC NHẬN)
    # =======================================================
    if xoa_kenh_hien_tai:
        channels_to_delete = [c for c in guild.channels if c.id != interaction.channel_id]
        deleted_count = 0
        
        await interaction.followup.send(f"⚠️ **BƯỚC 1/2: Bắt đầu XÓA {len(channels_to_delete)} kênh hiện có.** (TRỪ kênh hiện tại này)")
        
        for channel in channels_to_delete:
            try:
                await channel.delete()
                deleted_count += 1
            except discord.Forbidden:
                await interaction.followup.send(f"❌ Lỗi quyền: Bot không có quyền xóa kênh `{channel.name}`. Dừng quá trình xóa.", ephemeral=True)
                return 
            except Exception as e:
                print(f"Lỗi khi xóa kênh {channel.name}: {e}")

        await interaction.followup.send(f"✅ **Đã hoàn thành xóa {deleted_count} kênh.** Bắt đầu tạo kênh mới...")
        await asyncio.sleep(1) 

    # =======================================================
    # BƯỚC TẠO KÊNH MỚI VÀ GỬI EMBED
    # =======================================================
    kenh_da_tao = 0
    thoi_gian_bat_dau = time.time()
    
    await interaction.followup.send(f"🚀 **BƯỚC 2/2: Bắt đầu tạo {so_luong} kênh mới** theo mẫu `{ten_mau}`...")
    
    for i in range(1, so_luong + 1):
        so_thu_tu = f"{i:02}" 
        ten_kenh_moi = f"{ten_mau.lower()}{so_thu_tu}"
        ten_kenh_moi = ten_kenh_moi.replace(" ", "-") 

        try:
            # 1. TẠO KÊNH VÀ LƯU ĐỐI TƯỢNG KÊNH
            new_channel = await interaction.guild.create_text_channel(name=ten_kenh_moi)
            
            # 2. CHUẨN BỊ VÀ GỬI EMBED (CÓ ẢNH)
            
            # Xác định nội dung chính cho Embed
            if thong_diep:
                desc = thong_diep
            else:
                desc = f"Chào mừng đến với kênh mới {new_channel.mention}! Đây là kênh được tạo tự động."
                
            embed = discord.Embed(
                title=f"🎉 CHÀO MỪNG ĐẾN VỚI KÊNH {new_channel.name.upper()}!",
                description=desc,
                color=discord.Color.green()
            )
            
            # Thêm hình ảnh nếu URL được cung cấp
            if url_anh_chao:
                embed.set_image(url=url_anh_chao)
                
            # Gửi tin nhắn ping @everyone và Embed
            await new_channel.send(content="@everyone", embed=embed)
            
            kenh_da_tao += 1
            
            # Thông báo tiến độ (Sau mỗi 2 kênh)
            if kenh_da_tao % 2 == 0: 
                 await interaction.followup.send(f"✅ Đã tạo {kenh_da_tao}/{so_luong} kênh. Vẫn đang tiếp tục...", ephemeral=True)
                 
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi khi tạo kênh `{ten_kenh_moi}`: {e}", ephemeral=True)
            break
            
    thoi_gian_ket_thuc = time.time()
    tong_thoi_gian = thoi_gian_ket_thuc - thoi_gian_bat_dau
    
    await interaction.followup.send(
        f"🎉 **HOÀN TẤT TẠO KÊNH HÀNG LOẠT!**\n"
        f"Đã tạo thành công **{kenh_da_tao}** kênh.\n"
        f"Tổng thời gian: **{tong_thoi_gian:.2f} giây** (hoặc khoảng **{tong_thoi_gian / 60:.2f} phút**)"
    )


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