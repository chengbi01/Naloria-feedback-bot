import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import asyncio
import datetime
from dotenv import load_dotenv

# Tải biến môi trường
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
try:
    FEEDBACK_CHANNEL_ID = int(os.getenv("FEEDBACK_CHANNEL_ID"))
except:
    FEEDBACK_CHANNEL_ID = 0

# ====================================================================
# 1. HỆ THỐNG QUẢN LÝ DỮ LIỆU (JSON)
# ====================================================================
FILES = {
    "config": "config.json",
    "economy": "economy.json",
    "shop": "shop.json",
    "inventory": "inventory.json",
    "marriages": "marriages.json"
}

def load_json(filename):
    if not os.path.exists(filename):
        if filename == "config.json": return {"prefix": "!", "admin_role_id": None}
        if filename == "shop.json": return [] 
        return {} 
    try:
        with open(filename, "r", encoding='utf-8') as f:
            return json.load(f)
    except:
        return {} if filename != "shop.json" else []

def save_json(filename, data):
    with open(filename, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_prefix(bot, message):
    data = load_json(FILES["config"])
    return data.get("prefix", "!")

# ====================================================================
# 2. KHỞI TẠO BOT
# ====================================================================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=get_prefix, intents=intents)

def is_bot_admin(interaction: discord.Interaction):
    if interaction.user.guild_permissions.administrator: return True
    config = load_json(FILES["config"])
    role_id = config.get("admin_role_id")
    if role_id:
        role = interaction.guild.get_role(role_id)
        if role and role in interaction.user.roles: return True
    return False

# ====================================================================
# 3. CLASS VIEW (GIỮ NGUYÊN FEEDBACK + THÊM VIEW MARRY)
# ====================================================================

# --- [GIỮ NGUYÊN] VIEW FEEDBACK ---
class ChannelLauncherView(discord.ui.View):
    def __init__(self, bot_instance):
        super().__init__(timeout=None) 
        self.bot = bot_instance
    @discord.ui.button(label="Gửi Feedback", style=discord.ButtonStyle.primary, emoji="✍️", custom_id="persistent_feedback_button")
    async def launch_feedback_dm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Đã nhận lệnh! Kiểm tra DM nhé.", ephemeral=True)
        bot_name = self.bot.user.name
        embed = discord.Embed(title=f"✍️ Gửi Feedback cho {bot_name}", description="Nhập nội dung và gửi tại đây. Bot sẽ hỏi bạn muốn Ẩn danh hay Công khai.", color=discord.Color.gold())
        embed.set_footer(text=f"Hệ thống của {bot_name}")
        try: await interaction.user.send(embed=embed)
        except: await interaction.followup.send("❌ Không thể gửi DM. Vui lòng mở khóa tin nhắn.", ephemeral=True)

class AnonChoiceView(discord.ui.View):
    def __init__(self, content, author_id, feedback_id, bot):
        super().__init__(timeout=180)
        self.content = content
        self.author_id = author_id
        self.feedback_id = feedback_id
        self.bot = bot
        self.message = None
    async def send_fb(self, interaction, is_anon):
        channel = self.bot.get_channel(self.feedback_id)
        embed = discord.Embed(timestamp=discord.utils.utcnow())
        bot_name = self.bot.user.name
        if is_anon:
            embed.title = "🕵️ Phản hồi Ẩn danh"
            embed.color = discord.Color.dark_grey()
            embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/3665/3665909.png")
            embed.add_field(name="Nội dung:", value=f"> {self.content}", inline=False)
            embed.set_footer(text=f"{bot_name} Secret Mode")
        else:
            author = interaction.user
            embed.title = "📢 Phản hồi CÔNG KHAI"
            embed.color = discord.Color.teal()
            if author.avatar: embed.set_thumbnail(url=author.avatar.url)
            embed.add_field(name="Người gửi:", value=f"{author.mention} (`{author.name}`)", inline=True)
            embed.add_field(name="Nội dung:", value=f"> {self.content}", inline=False)
            embed.set_footer(text=f"ID: {author.id}")
        if channel:
            view = ChannelLauncherView(self.bot)
            msg = await channel.send(embed=embed, view=view)
            await msg.add_reaction("✅")
        self.stop()
        await interaction.followup.send(f"✅ Đã gửi {'Ẩn danh' if is_anon else 'Công khai'} thành công!", ephemeral=True)
    @discord.ui.button(label="Gửi Ẩn danh", style=discord.ButtonStyle.red, emoji="👤")
    async def anonymous_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id: return await interaction.response.send_message("❌ Không phải tin nhắn của bạn.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        await self.send_fb(interaction, True)
    @discord.ui.button(label="Gửi Công khai", style=discord.ButtonStyle.green, emoji="✅")
    async def public_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id: return await interaction.response.send_message("❌ Không phải tin nhắn của bạn.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        await self.send_fb(interaction, False)

# --- [MỚI] VIEW CẦU HÔN ---
class ProposalView(discord.ui.View):
    def __init__(self, author, target, item_name):
        super().__init__(timeout=60)
        self.author = author
        self.target = target
        self.item_name = item_name
        self.value = None

    async def on_timeout(self):
        for child in self.children: child.disabled = True
        if self.message:
            await self.message.edit(content=f"⏳ Lời cầu hôn đã hết hạn (Tự động từ chối).", view=self)

    @discord.ui.button(label="Đồng ý 💍", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message("❌ Nút này không dành cho bạn!", ephemeral=True)
        self.value = True
        for child in self.children: child.disabled = True
        
        # Nội dung khi thành công
        embed = discord.Embed(
            description=f"🎉 **{self.author.mention}** đã cầu hôn thành công **{self.target.mention}**, 2 bạn là cặp đôi hạnh phúc nhất lúc này! 💘",
            color=discord.Color.from_rgb(255, 105, 180)
        )
        await interaction.response.edit_message(content=None, embed=embed, view=self)
        self.stop()

    @discord.ui.button(label="Từ chối 💔", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message("❌ Nút này không dành cho bạn!", ephemeral=True)
        self.value = False
        for child in self.children: child.disabled = True
        await interaction.response.edit_message(content=f"😢 **{self.target.mention}** đã từ chối lời cầu hôn...", view=self)
        self.stop()

# --- [MỚI] VIEW LY HÔN ---
class DivorceView(discord.ui.View):
    def __init__(self, author, partner_id):
        super().__init__(timeout=60)
        self.author = author
        self.partner_id = partner_id
        self.value = None

    async def on_timeout(self):
        for child in self.children: child.disabled = True
        if self.message:
            await self.message.edit(content="🤔 Bạn đã im lặng... Hệ thống coi như bạn đã **suy nghĩ lại**.", view=self)

    @discord.ui.button(label="Xác nhận Ly hôn", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id: 
            return await interaction.response.send_message("❌ Chỉ người tạo lệnh mới được bấm nút này.", ephemeral=True)
        
        self.value = True
        self.stop()
        # Nội dung khi ly hôn
        embed = discord.Embed(
            description=f"💔 Chia buồn cặp đôi {self.author.mention} và <@{self.partner_id}> đã đường ai nấy đi.",
            color=discord.Color.dark_gray()
        )
        await interaction.response.edit_message(content=None, embed=embed, view=None)

    @discord.ui.button(label="Suy nghĩ lại", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id: 
            return await interaction.response.send_message("❌ Chỉ người tạo lệnh mới được bấm nút này.", ephemeral=True)
        self.value = False
        self.stop()
        await interaction.response.edit_message(content="😅 Phù... May mà bạn đã suy nghĩ lại.", view=None, embed=None)

# ====================================================================
# 4. CÁC LỆNH ADMIN (PREFIX + SLASH)
# ====================================================================
@bot.command()
@commands.has_permissions(administrator=True)
async def setprefix(ctx, new_prefix: str):
    config = load_json(FILES["config"])
    config["prefix"] = new_prefix
    save_json(FILES["config"], config)
    bot.command_prefix = new_prefix
    await ctx.send(f"✅ Đã đổi prefix thành: `{new_prefix}`")

@bot.command(aliases=['a', 'add'])
@commands.has_permissions(administrator=True)
async def add_money(ctx, type: str, user: discord.Member, amount: int):
    if type.lower() not in ['cash', 'c']: return
    economy = load_json(FILES["economy"])
    user_id = str(user.id)
    economy[user_id] = economy.get(user_id, 0) + amount
    save_json(FILES["economy"], economy)
    await ctx.send(f"✅ **ADMIN:** Cộng **{amount:,} VNĐ** cho {user.mention}. (Dư: {economy[user_id]:,})")

@bot.command(aliases=['s', 'sub'])
@commands.has_permissions(administrator=True)
async def sub_money(ctx, type: str, user: discord.Member, amount: int):
    if type.lower() not in ['cash', 'c']: return
    economy = load_json(FILES["economy"])
    user_id = str(user.id)
    economy[user_id] = max(0, economy.get(user_id, 0) - amount)
    save_json(FILES["economy"], economy)
    await ctx.send(f"✅ **ADMIN:** Trừ **{amount:,} VNĐ** của {user.mention}. (Dư: {economy[user_id]:,})")

@bot.tree.command(name="set_admin_role", description="Chọn Role Admin Bot")
@app_commands.describe(role="Role quản trị")
@app_commands.checks.has_permissions(administrator=True)
async def set_admin_role(interaction: discord.Interaction, role: discord.Role):
    config = load_json(FILES["config"])
    config["admin_role_id"] = role.id
    save_json(FILES["config"], config)
    await interaction.response.send_message(f"✅ Role Admin Bot: {role.mention}")

@bot.tree.command(name="item_create", description="Tạo vật phẩm Shop")
@app_commands.check(is_bot_admin)
async def item_create(interaction: discord.Interaction, name: str, price: int, emoji: str):
    shop = load_json(FILES["shop"])
    shop.append({"id": len(shop)+1, "name": name, "price": price, "emoji": emoji})
    save_json(FILES["shop"], shop)
    await interaction.response.send_message(f"✅ Đã thêm: {emoji} **{name}** - {price:,} VNĐ")

@bot.tree.command(name="item_delete", description="Xóa vật phẩm Shop")
@app_commands.check(is_bot_admin)
async def item_delete(interaction: discord.Interaction, item_index: int):
    shop = load_json(FILES["shop"])
    if item_index < 1 or item_index > len(shop): return await interaction.response.send_message("❌ ID không tồn tại.", ephemeral=True)
    deleted = shop.pop(item_index - 1)
    for idx, item in enumerate(shop): item["id"] = idx + 1
    save_json(FILES["shop"], shop)
    await interaction.response.send_message(f"🗑️ Đã xóa: {deleted['name']}")

@bot.tree.command(name="take_item", description="Tịch thu vật phẩm")
@app_commands.check(is_bot_admin)
async def take_item(interaction: discord.Interaction, user: discord.Member, item_index: int, quantity: int = 1):
    shop = load_json(FILES["shop"])
    if item_index < 1 or item_index > len(shop): return await interaction.response.send_message("❌ ID sai.", ephemeral=True)
    item_name = shop[item_index-1]["name"]
    inv = load_json(FILES["inventory"])
    uid = str(user.id)
    if uid not in inv or item_name not in inv[uid]: return await interaction.response.send_message("❌ User không có món này.", ephemeral=True)
    inv[uid][item_name] -= quantity
    if inv[uid][item_name] <= 0: del inv[uid][item_name]
    save_json(FILES["inventory"], inv)
    await interaction.response.send_message(f"👮 Đã tịch thu **{quantity}x {item_name}** của {user.mention}")

# ====================================================================
# 5. USER COMMANDS (SHOP, BUY, INV, GIFT)
# ====================================================================
@bot.command()
async def shop(ctx):
    shop = load_json(FILES["shop"])
    if not shop: return await ctx.send("🏪 Shop trống!")
    embed = discord.Embed(title=f"🏪 {bot.user.name} Shop Rings!", color=discord.Color.purple())
    desc = ""
    for item in shop: desc += f"**{item['id']:02}.** {item['emoji']} **{item['name']}**\n• Giá: {item['price']:,} VNĐ\n\n"
    embed.description = desc
    embed.set_footer(text=f"Trang 1/1 • {datetime.datetime.now().strftime('%H:%M %d/%m/%Y')}")
    await ctx.send(embed=embed)

@bot.command()
async def buy(ctx, idx: int, qty: int):
    if qty < 2: return await ctx.send("❌ Số lượng mua tối thiểu phải là 2!")
    shop = load_json(FILES["shop"])
    eco = load_json(FILES["economy"])
    inv = load_json(FILES["inventory"])
    uid = str(ctx.author.id)
    if idx < 1 or idx > len(shop): return await ctx.send("❌ ID sản phẩm sai.")
    item = shop[idx-1]
    cost = item['price'] * qty
    if eco.get(uid, 0) < cost: return await ctx.send(f"❌ Bạn không đủ tiền! Cần: {cost:,} VNĐ.")
    eco[uid] -= cost
    if uid not in inv: inv[uid] = {}
    inv[uid][item['name']] = inv[uid].get(item['name'], 0) + qty
    save_json(FILES["economy"], eco)
    save_json(FILES["inventory"], inv)
    await ctx.send(f"✅ Giao dịch thành công! Bạn đã mua **{qty}x {item['name']}**.\n💸 Tổng thiệt hại: {cost:,} VNĐ")

@bot.command(aliases=['inv', 'inventory'])
async def show_inv(ctx):
    inv = load_json(FILES["inventory"])
    uid = str(ctx.author.id)
    embed = discord.Embed(title=f"🎒 Kho đồ của {ctx.author.name}", color=discord.Color.blue())
    if uid not in inv or not inv[uid]: embed.description = "*Trống trơn...*"
    else:
        desc = ""
        for k, v in inv[uid].items(): desc += f"📦 **{k}**: {v} cái\n"
        embed.description = desc
    await ctx.send(embed=embed)

@bot.command()
async def gift(ctx, target: discord.Member, *, item_name: str):
    inv = load_json(FILES["inventory"])
    sid, tid = str(ctx.author.id), str(target.id)
    if sid not in inv or item_name not in inv[sid]: return await ctx.send(f"❌ Bạn không có vật phẩm **{item_name}**.")
    inv[sid][item_name] -= 1
    if inv[sid][item_name] <= 0: del inv[sid][item_name]
    if tid not in inv: inv[tid] = {}
    inv[tid][item_name] = inv[tid].get(item_name, 0) + 1
    save_json(FILES["inventory"], inv)
    await ctx.send(f"🎁 {ctx.author.mention} đã tặng **1x {item_name}** cho {target.mention}!")

# ====================================================================
# 6. HỆ THỐNG KẾT HÔN (MARRY 2.0 - FULL TÍNH NĂNG)
# ====================================================================

@bot.command(aliases=['mry', 'marry'])
async def marriage_system(ctx, arg1=None, arg2=None, *, arg3=None):
    data = load_json(FILES["marriages"])
    uid = str(ctx.author.id)
    
    # --- [1] LY HÔN (divorce) ---
    if arg1 and arg1.lower() == "divorce":
        if uid not in data: return await ctx.send("❌ Bạn đang độc thân mà?")
        
        embed = discord.Embed(title="💔 Đơn Ly Hôn", description="Bạn có chắc chắn muốn kết thúc cuộc hôn nhân này không?", color=discord.Color.red())
        partner_id = data[uid]["partner_id"]
        view = DivorceView(author=ctx.author, partner_id=partner_id)
        msg = await ctx.send(embed=embed, view=view)
        await view.wait()
        
        if view.value is True:
            # Xóa data cả 2
            pid = str(partner_id)
            if pid in data: del data[pid]
            if uid in data: del data[uid]
            save_json(FILES["marriages"], data)
        return

    # --- [2] TĂNG ĐIỂM YÊU THƯƠNG (luv) ---
    if arg1 and arg1.lower() == "luv":
        if uid not in data: return await ctx.send("❌ Bạn chưa kết hôn!")
        
        user_data = data[uid]
        last_luv = user_data.get("last_luv_timestamp", 0)
        now_ts = datetime.datetime.now().timestamp()
        
        # Check Cooldown 1 giờ (3600s)
        if now_ts - last_luv < 3600:
            remaining = int(3600 - (now_ts - last_luv))
            minutes = remaining // 60
            return await ctx.send(f"⏳ Bạn có thể gửi lời yêu thương đến người ấy trong **{minutes} phút** tới.", delete_after=5)

        # Cộng điểm
        pid = str(user_data["partner_id"])
        new_points = user_data.get("love_points", 0) + 1
        
        data[uid]["love_points"] = new_points
        data[uid]["last_luv_timestamp"] = now_ts
        if pid in data:
            data[pid]["love_points"] = new_points
        
        save_json(FILES["marriages"], data)
        
        partner_user = await bot.fetch_user(int(pid))
        embed = discord.Embed(
            description=f"💖 **{ctx.author.mention}** đang cảm thấy hạnh phúc vô bờ khi bên cạnh **{partner_user.mention}**! 🥰\n📈 **Điểm yêu thương:** {new_points}",
            color=discord.Color.pink()
        )
        await ctx.send(embed=embed)
        return

    # --- [3] TÙY CHỈNH PROFILE (image/thumbnail/caption) ---
    if arg1 and arg1.lower() in ["image", "thumbnail", "caption"]:
        if uid not in data: return await ctx.send("❌ Bạn chưa kết hôn!")
        if not arg2: return await ctx.send(f"❌ Vui lòng nhập nội dung! (VD: `{ctx.prefix}marry image [link]`)")
        
        content = arg2 
        if arg3: content = f"{arg2} {arg3}" # Nối chuỗi nếu có khoảng trắng

        key_map = {"image": "image_url", "thumbnail": "thumbnail_url", "caption": "caption"}
        key = key_map[arg1.lower()]
        
        # Cập nhật cho cả 2
        pid = str(data[uid]["partner_id"])
        data[uid][key] = content
        if pid in data: data[pid][key] = content
        
        save_json(FILES["marriages"], data)
        await ctx.send(f"✅ Đã cập nhật **{arg1}** thành công!")
        return

    # --- [4] XEM TRẠNG THÁI (Nếu không tag ai) ---
    if not ctx.message.mentions:
        # Nếu Độc thân
        if uid not in data:
            embed = discord.Embed(
                description="🍂 **Bạn đang chưa có tình yêu...**\nChắc hẳn bạn đã từng rất hạnh phúc phải không .....",
                color=discord.Color.light_grey()
            )
            return await ctx.send(embed=embed)
        
        # Nếu Đã kết hôn (Hiện Profile Đẹp)
        m_data = data[uid]
        partner_id = m_data["partner_id"]
        partner = await bot.fetch_user(partner_id)
        
        # Tính ngày
        m_date = datetime.datetime.fromtimestamp(m_data["marriage_date"])
        duration = (datetime.datetime.now() - m_date).days
        
        embed = discord.Embed(
            title=f"💞 {ctx.author.name}, bạn đang hạnh phúc với {partner.name}!",
            color=discord.Color.from_rgb(47, 49, 54)
        )
        
        desc = (
            f"📅 **Ngày kết hôn:** {m_date.strftime('%d tháng %m năm %Y')} ({duration} ngày)\n"
            f"💍 **Nhẫn đính hôn:** {m_data['ring_name']}\n"
            f"💗 **Điểm yêu thương:** {m_data.get('love_points', 0)} Điểm\n\n"
        )
        if m_data.get("caption"): desc += f"📝 *\"{m_data['caption']}\"*\n"
        desc += "\n`(づ ￣ ³￣)づ`"
        
        embed.description = desc
        if m_data.get("thumbnail_url"): embed.set_thumbnail(url=m_data["thumbnail_url"])
        if m_data.get("image_url"): embed.set_image(url=m_data["image_url"])
        
        await ctx.send(embed=embed)
        return

    # --- [5] CẦU HÔN (Nếu tag ai đó) ---
    target = ctx.message.mentions[0]
    
    # Logic kiểm tra trạng thái (Chặn ngoại tình/cướp bồ)
    if uid in data:
        p_name = (await bot.fetch_user(data[uid]["partner_id"])).name
        return await ctx.send(embed=discord.Embed(description=f"❌ Bạn quên mất tình yêu **{p_name}** (kết hôn cùng) rồi hay sao? 😠", color=discord.Color.red()))
    
    if str(target.id) in data:
        p_name_target = (await bot.fetch_user(data[str(target.id)]["partner_id"])).name
        return await ctx.send(embed=discord.Embed(description=f"❌ **{target.name}** đã còn bạn đời tri kỉ là **{p_name_target}** (kết hôn cùng) rồi! 😢", color=discord.Color.red()))

    if target.id == ctx.author.id or target.bot: return await ctx.send("❌ Đối tượng không hợp lệ.")

    # Kiểm tra nhẫn
    try: ring_idx = int(arg2)
    except: return await ctx.send("❌ Thiếu số thứ tự nhẫn! (VD: `!marry @User 1`)")
    
    shop_data = load_json(FILES["shop"])
    if ring_idx < 1 or ring_idx > len(shop_data): return await ctx.send("❌ Nhẫn không tồn tại.")
    ring = shop_data[ring_idx-1]
    
    inv = load_json(FILES["inventory"])
    if uid not in inv or ring["name"] not in inv[uid]: return await ctx.send(f"❌ Bạn chưa mua nhẫn **{ring['name']}**!")

    # Gửi lời cầu hôn
    embed = discord.Embed(
        title="💍 Lời Cầu Hôn",
        description=f"**{target.mention}**, bạn nhận được lời cầu hôn từ **{ctx.author.mention}**!\n\n💎 Vật phẩm đính ước: **{ring['emoji']} {ring['name']}**",
        color=discord.Color.pink()
    )
    view = ProposalView(author=ctx.author, target=target, item_name=ring["name"])
    msg = await ctx.send(content=target.mention, embed=embed, view=view)
    
    await view.wait()
    
    if view.value is True:
        # Lưu dữ liệu Hôn nhân
        now_ts = datetime.datetime.now().timestamp()
        marriage_info = {
            "partner_id": target.id,
            "marriage_date": now_ts,
            "ring_name": f"{ring['emoji']} {ring['name']}",
            "love_points": 0,
            "image_url": "",
            "thumbnail_url": "",
            "caption": "",
            "last_luv_timestamp": 0
        }
        
        data[uid] = marriage_info.copy()
        marriage_info["partner_id"] = ctx.author.id
        data[str(target.id)] = marriage_info
        
        save_json(FILES["marriages"], data)
        
        # Trừ nhẫn
        inv[uid][ring["name"]] -= 1
        if inv[uid][ring["name"]] <= 0: del inv[uid][ring["name"]]
        save_json(FILES["inventory"], inv)

# ====================================================================
# SỰ KIỆN BOT
# ====================================================================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.add_view(ChannelLauncherView(bot))
    try: await bot.tree.sync()
    except Exception as e: print(e)

@bot.event
async def on_message(message):
    if message.author.bot: return
    # Xử lý DM Feedback (Giữ nguyên)
    if isinstance(message.channel, discord.DMChannel):
        if len(message.content) < 2: return
        view = AnonChoiceView(message.content, message.author.id, FEEDBACK_CHANNEL_ID, bot)
        embed = discord.Embed(title="❓ Gửi Phản hồi", description=f"Nội dung: **{message.content}**\nChọn chế độ gửi (Hủy sau 3 phút).", color=discord.Color.gold())
        msg = await message.author.send(embed=embed, view=view)
        view.message = msg
        return
    await bot.process_commands(message)

bot.run(TOKEN)