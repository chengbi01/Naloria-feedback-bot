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
# 1. HỆ THỐNG QUẢN LÝ DỮ LIỆU
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
# 3. CLASS VIEW (NÚT BẤM)
# ====================================================================

# --- VIEW FEEDBACK ---
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

# --- VIEW CẦU HÔN ---
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

# --- VIEW LY HÔN ---
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
# 4. CÁC LỆNH ADMIN
# ====================================================================
@bot.tree.command(name="set_prefix", description="Đổi dấu lệnh (Prefix) cho Bot")
@app_commands.describe(new_prefix="Nhập ký tự muốn đổi (Ví dụ: ! hoặc . hoặc ?)")
@app_commands.checks.has_permissions(administrator=True)
async def set_prefix(interaction: discord.Interaction, new_prefix: str):
    config = load_json(FILES["config"])
    config["prefix"] = new_prefix
    save_json(FILES["config"], config)
    await interaction.response.send_message(embed=discord.Embed(description=f"✅ Đã đổi prefix thành: `{new_prefix}`", color=discord.Color.green()))

@bot.tree.command(name="set_admin_role", description="Chọn Role Admin Bot")
@app_commands.describe(role="Role quản trị")
@app_commands.checks.has_permissions(administrator=True)
async def set_admin_role(interaction: discord.Interaction, role: discord.Role):
    config = load_json(FILES["config"])
    config["admin_role_id"] = role.id
    save_json(FILES["config"], config)
    await interaction.response.send_message(embed=discord.Embed(description=f"✅ Đã thiết lập Role Admin Bot: {role.mention}", color=discord.Color.green()))

@bot.tree.command(name="item_create", description="Tạo vật phẩm Shop")
@app_commands.check(is_bot_admin)
async def item_create(interaction: discord.Interaction, name: str, price: int, emoji: str):
    shop = load_json(FILES["shop"])
    shop.append({"id": len(shop)+1, "name": name, "price": price, "emoji": emoji})
    save_json(FILES["shop"], shop)
    await interaction.response.send_message(embed=discord.Embed(description=f"✅ Đã thêm: {emoji} **{name}** - {price:,} VNĐ", color=discord.Color.green()))

@bot.tree.command(name="item_delete", description="Xóa vật phẩm Shop")
@app_commands.check(is_bot_admin)
async def item_delete(interaction: discord.Interaction, item_index: int):
    shop = load_json(FILES["shop"])
    if item_index < 1 or item_index > len(shop): return await interaction.response.send_message(embed=discord.Embed(description="❌ ID không tồn tại.", color=discord.Color.red()), ephemeral=True)
    deleted = shop.pop(item_index - 1)
    for idx, item in enumerate(shop): item["id"] = idx + 1
    save_json(FILES["shop"], shop)
    await interaction.response.send_message(embed=discord.Embed(description=f"🗑️ Đã xóa: {deleted['name']}", color=discord.Color.green()))

@bot.tree.command(name="take_item", description="Tịch thu vật phẩm")
@app_commands.check(is_bot_admin)
async def take_item(interaction: discord.Interaction, user: discord.Member, item_index: int, quantity: int = 1):
    shop = load_json(FILES["shop"])
    if item_index < 1 or item_index > len(shop): return await interaction.response.send_message(embed=discord.Embed(description="❌ ID sai.", color=discord.Color.red()), ephemeral=True)
    item_name = shop[item_index-1]["name"]
    inv = load_json(FILES["inventory"])
    uid = str(user.id)
    if uid not in inv or item_name not in inv[uid]: return await interaction.response.send_message(embed=discord.Embed(description="❌ User không có món này.", color=discord.Color.red()), ephemeral=True)
    inv[uid][item_name] -= quantity
    if inv[uid][item_name] <= 0: del inv[uid][item_name]
    save_json(FILES["inventory"], inv)
    await interaction.response.send_message(embed=discord.Embed(description=f"👮 Đã tịch thu **{quantity}x {item_name}** của {user.mention}", color=discord.Color.orange()))

@bot.command(aliases=['ac', 'add'])
@commands.has_permissions(administrator=True)
async def add_money(ctx, user: discord.Member, amount: int):
    economy = load_json(FILES["economy"])
    user_id = str(user.id)
    economy[user_id] = economy.get(user_id, 0) + amount
    save_json(FILES["economy"], economy)
    await ctx.send(embed=discord.Embed(description=f"✅ **ADMIN:** Cộng **{amount:,} VNĐ** cho {user.mention}.\n💰 Số dư mới: {economy[user_id]:,} VNĐ", color=discord.Color.green()))

@bot.command(aliases=['sc', 'sub'])
@commands.has_permissions(administrator=True)
async def sub_money(ctx, user: discord.Member, amount: int):
    economy = load_json(FILES["economy"])
    user_id = str(user.id)
    economy[user_id] = max(0, economy.get(user_id, 0) - amount)
    save_json(FILES["economy"], economy)
    await ctx.send(embed=discord.Embed(description=f"✅ **ADMIN:** Trừ **{amount:,} VNĐ** của {user.mention}.\n💰 Số dư mới: {economy[user_id]:,} VNĐ", color=discord.Color.green()))

# ====================================================================
# 5. USER COMMANDS
# ====================================================================
@bot.command()
async def shop(ctx):
    shop = load_json(FILES["shop"])
    if not shop: return await ctx.send(embed=discord.Embed(description="🏪 Shop trống!", color=discord.Color.gold()))
    embed = discord.Embed(title=f"🏪 {bot.user.name} Shop", color=discord.Color.purple())
    desc = ""
    for item in shop: desc += f"**{item['id']:02}.** {item['emoji']} **{item['name']}**\n• Giá: {item['price']:,} VNĐ\n\n"
    embed.description = desc
    embed.set_footer(text=f"Cập nhật: {datetime.datetime.now().strftime('%H:%M')}")
    await ctx.send(embed=embed)

@bot.command()
async def buy(ctx, idx: int, qty: int = 1):
    if qty < 1: return await ctx.send(embed=discord.Embed(description="❌ Số lượng mua tối thiểu là 1.", color=discord.Color.red()))
    shop = load_json(FILES["shop"])
    eco = load_json(FILES["economy"])
    inv = load_json(FILES["inventory"])
    uid = str(ctx.author.id)
    if idx < 1 or idx > len(shop): return await ctx.send(embed=discord.Embed(description="❌ ID sản phẩm sai.", color=discord.Color.red()))
    item = shop[idx-1]
    cost = item['price'] * qty
    if eco.get(uid, 0) < cost: return await ctx.send(embed=discord.Embed(description=f"❌ Thiếu tiền! Cần: {cost:,} VNĐ.", color=discord.Color.red()))
    eco[uid] -= cost
    if uid not in inv: inv[uid] = {}
    inv[uid][item['name']] = inv[uid].get(item['name'], 0) + qty
    save_json(FILES["economy"], eco)
    save_json(FILES["inventory"], inv)
    await ctx.send(embed=discord.Embed(description=f"✅ Giao dịch thành công! Mua **{qty}x {item['name']}**.\n💸 Tổng tiền: {cost:,} VNĐ", color=discord.Color.green()))

@bot.command(aliases=['inv', 'inventory'])
async def show_inv(ctx):
    inv = load_json(FILES["inventory"])
    uid = str(ctx.author.id)
    embed = discord.Embed(title=f"🎒 Túi đồ của {ctx.author.name}", color=discord.Color.blue())
    if uid not in inv or not inv[uid]: embed.description = "*Trống trơn.*"
    else:
        desc = ""
        for k, v in inv[uid].items(): desc += f"📦 **{k}**: {v}\n"
        embed.description = desc
    await ctx.send(embed=embed)

@bot.command()
async def gift(ctx, target: discord.Member, *, item_name: str):
    inv = load_json(FILES["inventory"])
    sid, tid = str(ctx.author.id), str(target.id)
    if sid not in inv or item_name not in inv[sid]: return await ctx.send(embed=discord.Embed(description=f"❌ Bạn không có **{item_name}**.", color=discord.Color.red()))
    inv[sid][item_name] -= 1
    if inv[sid][item_name] <= 0: del inv[sid][item_name]
    if tid not in inv: inv[tid] = {}
    inv[tid][item_name] = inv[tid].get(item_name, 0) + 1
    save_json(FILES["inventory"], inv)
    await ctx.send(embed=discord.Embed(description=f"🎁 {ctx.author.mention} đã tặng **{item_name}** cho {target.mention}!", color=discord.Color.green()))

# ====================================================================
# 6. MARRY SYSTEM (Full Embed)
# ====================================================================

@bot.command()
async def divorce(ctx):
    data = load_json(FILES["marriages"])
    uid = str(ctx.author.id)
    if uid not in data: return await ctx.send(embed=discord.Embed(description="❌ Bạn đang độc thân mà?", color=discord.Color.red()))
    embed = discord.Embed(title="💔 Đơn Ly Hôn", description="Bạn có chắc chắn muốn kết thúc không?", color=discord.Color.red())
    partner_id = data[uid]["partner_id"]
    view = DivorceView(author=ctx.author, partner_id=partner_id)
    msg = await ctx.send(embed=embed, view=view)
    await view.wait()
    if view.value is True:
        pid = str(partner_id)
        if pid in data: del data[pid]
        if uid in data: del data[uid]
        save_json(FILES["marriages"], data)

@bot.command(aliases=['mry', 'marry'])
async def marriage_system(ctx, arg1=None, arg2=None, *, arg3=None):
    data = load_json(FILES["marriages"])
    uid = str(ctx.author.id)
    
    # --- [1] LUV ---
    if arg1 and arg1.lower() == "luv":
        if uid not in data: return await ctx.send(embed=discord.Embed(description="❌ Bạn chưa kết hôn!", color=discord.Color.red()))
        user_data = data[uid]
        last_luv = user_data.get("last_luv_timestamp", 0)
        now_ts = datetime.datetime.now().timestamp()
        if now_ts - last_luv < 3600:
            remaining = int(3600 - (now_ts - last_luv))
            return await ctx.send(embed=discord.Embed(description=f"⏳ Chờ **{remaining//60} phút** nữa nhé.", color=discord.Color.gold()), delete_after=5)
        pid = str(user_data["partner_id"])
        new_points = user_data.get("love_points", 0) + 1
        data[uid]["love_points"] = new_points
        data[uid]["last_luv_timestamp"] = now_ts
        if pid in data: data[pid]["love_points"] = new_points
        save_json(FILES["marriages"], data)
        partner_user = await bot.fetch_user(int(pid))
        return await ctx.send(embed=discord.Embed(description=f"💖 **{ctx.author.mention}** đã gửi yêu thương đến **{partner_user.mention}**! (Điểm: {new_points})", color=discord.Color.pink()))

    # --- [2] CUSTOMIZE ---
    if arg1 and arg1.lower() in ["image", "thumbnail", "caption"]:
        if uid not in data: return await ctx.send(embed=discord.Embed(description="❌ Bạn chưa kết hôn!", color=discord.Color.red()))
        cmd_type = arg1.lower()
        content = None
        if cmd_type in ["image", "thumbnail"]:
            if ctx.message.attachments: content = ctx.message.attachments[0].url
            elif arg2: content = arg2
            else: return await ctx.send(embed=discord.Embed(description=f"❌ Vui lòng đính kèm ảnh!", color=discord.Color.red()))
        elif cmd_type == "caption":
            if not arg2: return await ctx.send(embed=discord.Embed(description=f"❌ Vui lòng nhập nội dung!", color=discord.Color.red()))
            content = arg2
            if arg3: content = f"{arg2} {arg3}"
        
        key_map = {"image": "image_url", "thumbnail": "thumbnail_url", "caption": "caption"}
        key = key_map[cmd_type]
        pid = str(data[uid]["partner_id"])
        data[uid][key] = content
        if pid in data: data[pid][key] = content
        save_json(FILES["marriages"], data)
        return await ctx.send(embed=discord.Embed(description=f"✅ Đã cập nhật **{cmd_type}** thành công!", color=discord.Color.green()))

    # --- [3] STATUS ---
    if not ctx.message.mentions:
        if uid not in data: return await ctx.send(embed=discord.Embed(description="🍂 **Bạn đang chưa có tình yêu...**\nChắc hẳn bạn đã từng rất hạnh phúc phải không .....", color=discord.Color.light_grey()))
        m_data = data[uid]
        try: partner = await bot.fetch_user(m_data["partner_id"]); p_name = partner.name
        except: p_name = "Unknown"
        m_date = datetime.datetime.fromtimestamp(m_data["marriage_date"])
        duration = (datetime.datetime.now() - m_date).days
        embed = discord.Embed(title=f"💞 {ctx.author.name} x {p_name}", color=discord.Color.from_rgb(47, 49, 54))
        desc = f"📅 **Ngày cưới:** {m_date.strftime('%d/%m/%Y')} ({duration} ngày)\n💍 **Nhẫn:** {m_data['ring_name']}\n💗 **Love:** {m_data.get('love_points', 0)}"
        if m_data.get("caption"): desc += f"\n\n📝 *\"{m_data['caption']}\"*"
        desc += "\n`(づ ￣ ³￣)づ`"
        embed.description = desc
        if m_data.get("thumbnail_url"): embed.set_thumbnail(url=m_data["thumbnail_url"])
        if m_data.get("image_url"): embed.set_image(url=m_data["image_url"])
        return await ctx.send(embed=embed)

    # --- [4] PROPOSAL ---
    target = ctx.message.mentions[0]
    if uid in data:
        p_name = (await bot.fetch_user(data[uid]["partner_id"])).name
        return await ctx.send(embed=discord.Embed(description=f"❌ Bạn quên mất tình yêu **{p_name}** rồi sao?", color=discord.Color.red()))
    if str(target.id) in data:
        p_name_target = (await bot.fetch_user(data[str(target.id)]["partner_id"])).name
        return await ctx.send(embed=discord.Embed(description=f"❌ **{target.name}** đã có tri kỉ là **{p_name_target}** rồi!", color=discord.Color.red()))
    if target.id == ctx.author.id or target.bot: return await ctx.send(embed=discord.Embed(description="❌ Đối tượng không hợp lệ.", color=discord.Color.red()))
    try: ring_idx = int(arg2)
    except: return await ctx.send(embed=discord.Embed(description=f"❌ Thiếu mã nhẫn! VD: `{ctx.prefix}marry {target.name} 1`", color=discord.Color.red()))
    shop = load_json(FILES["shop"])
    if ring_idx < 1 or ring_idx > len(shop): return await ctx.send(embed=discord.Embed(description="❌ Mã nhẫn không đúng.", color=discord.Color.red()))
    ring = shop[ring_idx-1]
    inv = load_json(FILES["inventory"])
    if uid not in inv or ring["name"] not in inv[uid]: return await ctx.send(embed=discord.Embed(description=f"❌ Bạn chưa có nhẫn **{ring['name']}**.", color=discord.Color.red()))

    embed = discord.Embed(title="💍 Lời Cầu Hôn", description=f"**{target.mention}**, {ctx.author.mention} cầu hôn bạn bằng **{ring['emoji']} {ring['name']}**!", color=discord.Color.pink())
    view = ProposalView(author=ctx.author, target=target, item_name=ring["name"])
    await ctx.send(content=target.mention, embed=embed, view=view)
    await view.wait()
    if view.value is True:
        now_ts = datetime.datetime.now().timestamp()
        marriage_info = {"partner_id": target.id, "marriage_date": now_ts, "ring_name": f"{ring['emoji']} {ring['name']}", "love_points": 0, "image_url": "", "thumbnail_url": "", "caption": "", "last_luv_timestamp": 0}
        data[uid] = marriage_info.copy()
        marriage_info["partner_id"] = ctx.author.id
        data[str(target.id)] = marriage_info
        save_json(FILES["marriages"], data)
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
    if isinstance(message.channel, discord.DMChannel):
        if len(message.content) < 2: return
        view = AnonChoiceView(message.content, message.author.id, FEEDBACK_CHANNEL_ID, bot)
        embed = discord.Embed(title="❓ Gửi Phản hồi", description=f"Nội dung: **{message.content}**\nChọn chế độ gửi (Hủy sau 3 phút).", color=discord.Color.gold())
        msg = await message.author.send(embed=embed, view=view)
        view.message = msg
        return
    await bot.process_commands(message)

bot.run(TOKEN)