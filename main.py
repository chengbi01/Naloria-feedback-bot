# [ĐẦU FILE CODE BOT CỦA BẠN]

import discord
from discord.ext import commands
import os
from dotenv import load_dotenv # Dùng để đọc file .env khi chạy LOCAL

# Tải biến môi trường từ file .env (CHỈ CHẠY KHI Ở MÁY CÁ NHÂN)
# Khi chạy trên Render, nó sẽ tự động bỏ qua file .env và đọc biến trực tiếp.
load_dotenv() 

# ====================================================================
# THIẾT LẬP CẦN THAY THẾ (LẤY TỪ BIẾN MÔI TRƯỜNG)
# ====================================================================

# Lấy TOKEN từ biến môi trường "DISCORD_TOKEN"
TOKEN = os.getenv("DISCORD_TOKEN") 

# Lấy ID kênh từ biến môi trường "FEEDBACK_CHANNEL_ID"
try:
    # Đảm bảo ID kênh là số nguyên
    FEEDBACK_CHANNEL_ID = int(os.getenv("FEEDBACK_CHANNEL_ID")) 
except (TypeError, ValueError):
    # Xử lý nếu biến không tồn tại hoặc không phải số
    print("!!! LỖI QUAN TRỌNG: Biến FEEDBACK_CHANNEL_ID chưa được cấu hình đúng. !!!")
    FEEDBACK_CHANNEL_ID = 0

# ====================================================================
# 1. LỚP VIEW XỬ LÝ LỰA CHỌN TRONG DM (ANON/PUBLIC)
# ====================================================================

class AnonChoiceView(discord.ui.View):
    def __init__(self, original_content, original_author_id, feedback_channel_id, bot_instance):
        super().__init__(timeout=180) # Hết thời gian sau 3 phút
        self.original_content = original_content
        self.original_author_id = original_author_id
        self.feedback_channel_id = feedback_channel_id
        self.bot = bot_instance
        self.message = None # Lưu trữ tin nhắn chứa nút trong DM

    async def on_timeout(self):
        """Xử lý khi View hết thời gian chờ."""
        for item in self.children:
            item.disabled = True
        
        if self.message:
            await self.message.edit(
                content="⚠️ **Lựa chọn phản hồi đã hết thời gian (3 phút).** Vui lòng gửi lại tin nhắn nếu bạn muốn gửi phản hồi.", 
                embed=None, 
                view=self
            )

    async def send_feedback(self, interaction: discord.Interaction, is_anonymous: bool):
        feedback_channel = self.bot.get_channel(self.feedback_channel_id)

        # 1. TẠO EMBED PHẢN HỒI GỬI ĐẾN ADMIN
        if is_anonymous:
            title = ":envelope_with_arrow: Phản hồi Ẩn danh Mới"
            footer_text = "Cảm ơn quý khách đã feedback, Naloria sẽ cố gắng hoàn thiện hơn trong tương lai ❤️"
            color = discord.Color.from_rgb(255, 99, 71)
        else:
            author = interaction.user
            title = f":loudspeaker: Phản hồi CÔNG KHAI từ {author.display_name}"
            footer_text = "Cảm ơn quý khách đã feedback, Naloria sẽ cố gắng hoàn thiện hơn trong tương lai ❤️"
            color = discord.Color.blue()
        
        embed_feedback = discord.Embed(
            title=title,
            description=self.original_content,
            color=color
        )
        embed_feedback.set_footer(text=footer_text)
        
        # 2. Gửi đến kênh Admin và thêm reaction
        sent_message = await feedback_channel.send(embed=embed_feedback)
        await sent_message.add_reaction("✅")

        # 3. Vô hiệu hóa nút trong DM và dừng view
        self.stop()
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=self)

        # 4. Gửi xác nhận cho người dùng trong DM
        confirmation_msg = "✅ Phản hồi của bạn đã được gửi thành công!"
        confirmation_msg += " (Ẩn danh)" if is_anonymous else " (Công khai)"
            
        embed_confirmation = discord.Embed(
            title="Gửi Thành Công",
            description=confirmation_msg,
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed_confirmation, ephemeral=True)


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
    def __init__(self):
        # Phải đặt timeout=None để View cố định không bị xóa khi bot khởi động lại
        super().__init__(timeout=None) 
        
    # custom_id là cần thiết cho persistent view
    @discord.ui.button(label="Gửi Phản hồi/Góp ý", style=discord.ButtonStyle.primary, emoji="📬", custom_id="persistent_feedback_button")
    async def launch_feedback_dm(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Xử lý khi người dùng nhấn nút trong kênh."""
        
        await interaction.response.send_message(
            "Đã nhận được yêu cầu! **Vui lòng kiểm tra Tin nhắn Trực tiếp (DM)** để tiếp tục.",
            ephemeral=True
        )

        try:
            # Gửi hướng dẫn để người dùng biết họ cần gõ nội dung phản hồi
            await interaction.user.send(
                "Chào bạn! Vui lòng **gõ và gửi nội dung phản hồi** của bạn vào kênh DM này. Sau đó, tôi sẽ hỏi bạn muốn gửi **Ẩn danh** hay **Công khai**."
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Lỗi: Tôi không thể gửi DM cho bạn. Vui lòng kiểm tra cài đặt quyền riêng tư.", 
                ephemeral=True
            )


# ====================================================================
# 3. CẤU HÌNH VÀ SỰ KIỆN BOT
# ====================================================================

# Thiết lập Intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.dm_messages = True

# Khởi tạo Bot
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Bot đã đăng nhập với tên: {bot.user} (ID: {bot.user.id})')
    
    # Đăng ký View cố định (Persistent View)
    # Đảm bảo các nút trong kênh vẫn hoạt động sau khi bot khởi động lại
    bot.add_view(ChannelLauncherView()) 
    
    # Thiết lập trạng thái hoạt động của Bot
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching, 
        name="DM để gửi phản hồi công khai/ẩn danh"
    ))

    feedback_channel = bot.get_channel(FEEDBACK_CHANNEL_ID)
    if not feedback_channel:
        print(f'!!! LỖI QUAN TRỌNG: Không tìm thấy Kênh Phản hồi với ID: {FEEDBACK_CHANNEL_ID} !!!')
    else:
        print(f'Kênh Phản hồi được thiết lập là: #{feedback_channel.name}')


@bot.event
async def on_message(message):
    # 1. Bỏ qua tin nhắn từ chính bot
    if message.author == bot.user:
        return

    # 2. XỬ LÝ TIN NHẮN TRỰC TIẾP (DM)
    if isinstance(message.channel, discord.DMChannel):
        if len(message.content.strip()) < 5:
             await message.author.send("Tin nhắn quá ngắn để được coi là phản hồi. Vui lòng cung cấp nội dung chi tiết hơn.")
             return

        try:
            # 3. Tạo View lựa chọn Anon/Public
            view = AnonChoiceView(
                original_content=message.content,
                original_author_id=message.author.id,
                feedback_channel_id=FEEDBACK_CHANNEL_ID,
                bot_instance=bot
            )

            # 4. Tạo Embed hỏi người dùng
            preview_content = message.content[:50] + ("..." if len(message.content) > 50 else "")
            embed_choice = discord.Embed(
                title="❓ Lựa chọn Gửi Phản hồi",
                description=f"Bạn muốn gửi nội dung phản hồi này như thế nào? (Nội dung của bạn: **{preview_content}**)",
                color=discord.Color.gold()
            )
            embed_choice.set_footer(text="Nếu bạn không chọn trong 3 phút, tin nhắn sẽ bị hủy và bạn cần gửi lại.")
            
            # 5. Gửi Embed kèm nút cho người dùng
            sent_message = await message.author.send(embed=embed_choice, view=view)
            
            # GÁN TIN NHẮN VÀO VIEW để có thể chỉnh sửa nó khi timeout
            view.message = sent_message
            
        except Exception as e:
            print(f"Lỗi khi xử lý DM và gửi lựa chọn: {e}")
            await message.author.send("❌ Đã xảy ra lỗi không xác định khi xử lý phản hồi của bạn.")

    # Cho phép các lệnh khác của bot vẫn hoạt động
    await bot.process_commands(message)

# ====================================================================
# 4. LỆNH ADMIN ĐỂ TẠO THÔNG BÁO TRONG KÊNH
# ====================================================================

@bot.command(name='setup_feedback')
@commands.has_permissions(administrator=True) # Chỉ cho phép Admin sử dụng lệnh này
async def setup_feedback(ctx):
    """Lệnh Admin: Gửi Embed thông báo phản hồi vào kênh để người dùng tương tác."""
    
    if isinstance(ctx.channel, discord.DMChannel):
        return await ctx.send("Lệnh này chỉ có thể được sử dụng trong máy chủ (server).")

    # TẠO EMBED THÔNG BÁO
    embed = discord.Embed(
        title="<a:tim3:1440201393636900915> Kênh Phản hồi & Góp ý Chính thức <a:tim3:1440201393636900915>",
        description=(
            "Hãy dành chút thời gian để feedback để giúp chúng mình hoàn thiện tốt hơn trong tương lai nhé. <a:tim4:1432983116980686901> \n\n"
            "**CÁCH SỬ DỤNG:**\n"
            "1. Nhấn nút **'Gửi Phản hồi/Góp ý'** bên dưới.\n"
            "2. Bot sẽ mở **Tin nhắn Trực tiếp (DM)** với bạn.\n"
            "3. **Gõ nội dung** phản hồi của bạn vào DM đó. Bot sẽ hỏi bạn muốn gửi **Ẩn danh** hay **Công khai**."
        ),
        color=discord.Color.pink()
    )
    embed.set_footer(text="Phản hồi của bạn sẽ được chuyển đến đội ngũ quản trị.")

    # Gửi Embed kèm Nút (sử dụng ChannelLauncherView đã đăng ký)
    await ctx.send(embed=embed, view=ChannelLauncherView())

    # Xóa lệnh gọi ban đầu (tùy chọn)
    try:
        await ctx.message.delete()
    except:
        pass


# ====================================================================
# 5. CHẠY BOT
# ====================================================================
# Dòng 258
try:
    # Nếu TOKEN đã được đọc từ biến môi trường, chỉ cần chạy bot
    if not TOKEN:
        print("LỖI: TOKEN không được cấu hình. Vui lòng kiểm tra biến môi trường DISCORD_TOKEN.")
    else:
        bot.run(TOKEN)

except discord.HTTPException as e:
    # ... (Phần xử lý lỗi HTTP giữ nguyên)
    if e.status == 401:
        print("LỖI: Token Bot không hợp lệ. Vui lòng kiểm tra lại TOKEN.")
    else:
        raise