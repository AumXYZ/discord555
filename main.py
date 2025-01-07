import discord
from discord.ext import commands
from discord import ui
from datetime import datetime
import json
import os
import pytz
from table2ascii import table2ascii as t2a, PresetStyle

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
ALLOWED_USERS = [1112085770904281158, 871833855462617118, 852854008602820626]
    
class MyBot(discord.Client):
    def __init__(self, intents):
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)

bot = MyBot(intents)

DATA_FILE = 'inventory_data.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
        return data.get('inventory', {}), data.get('daily_profit', {}), data.get('daily_buy', {}), data.get('log', [])
    else:
        return {}, {}, {}, []

inventory, daily_profit, daily_buy, log = load_data()

def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump({'inventory': inventory, 'daily_profit': daily_profit, 'daily_buy': daily_buy, 'log': log}, f)

def log_event(action, item_key, price, timestamp):
    log.append({
        "action": action,
        "item_key": item_key,
        "price": price,
        "timestamp": timestamp
    })
    save_data()

def is_user_allowed(interaction: discord.Interaction):
    return interaction.user.id in ALLOWED_USERS

LOG_CHANNEL_ID = 1322639267784167545  # ระบุ Channel ID ที่ต้องการส่ง log

async def send_log_to_channel(bot, log_message):
    """ส่ง log ไปยัง Channel ที่ระบุ"""
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(log_message)

def get_thailand_time():
    tz = pytz.timezone('Asia/Bangkok')
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.tree.sync()
    print("Commands synced!")

def update_item_keys():
    global inventory
    updated_inventory = {}
    unique_id_counter = 1  

    for name, items in inventory.items():
        items.sort(key=lambda x: x["unique_id"])

        for item in items:
            item["unique_id"] = unique_id_counter
            item_key = f"{unique_id_counter}. {name}" 
            item["item_key"] = item_key
            unique_id_counter += 1 

        updated_inventory[name] = items
    inventory = updated_inventory
    save_data()

@bot.tree.command(name="buy", description="เพิ่มสินค้าเข้ารายการ")
async def buy(interaction: discord.Interaction, name: str, status: str, price: int):
    if not is_user_allowed(interaction):
        await interaction.response.send_message("คุณไม่มีสิทธิ์ใช้คำสั่งนี้!", ephemeral=True)
        return
    timestamp = get_thailand_time()

    if name not in inventory:
        inventory[name] = []

    inventory[name].append({
        "item_key": "",
        "status": status,
        "price": price,
        "unique_id": 0 
    })

    update_item_keys()

    date_today = datetime.now().strftime("%Y-%m-%d")
    if date_today in daily_buy:
        daily_buy[date_today] += price
    else:
        daily_buy[date_today] = price

    save_data()

    log_message = f"🛒 **Buy Log**\nสินค้า: `{name}`\nสถานะ: `{status}`\nราคา: `{price}` บาท\nเพิ่มเมื่อ: `{timestamp}`"
    await send_log_to_channel(bot, log_message)

    embed = discord.Embed(
        title="เพิ่มสินค้า",
        description=f"รับสินค้า {name} สถานะ {status} ราคา {price} บาท เข้ารายการแล้ว!",
        color=discord.Color.green(),
    )
    embed.set_footer(text=f"เพิ่มเมื่อ {timestamp}")
    if not interaction.response.is_done():
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="sell", description="ขายสินค้าและคำนวณกำไร")
async def sell(interaction: discord.Interaction, unique_id: int, price: int):
            if not is_user_allowed(interaction):
                await interaction.response.send_message("คุณไม่มีสิทธิ์ใช้คำสั่งนี้!", ephemeral=True)
                return
            timestamp = get_thailand_time()

            for name, items in inventory.items():
                for item in items:
                    if item["unique_id"] == unique_id:
                        buy_price = item["price"]
                        profit = price - buy_price

                        log_event("ขายสินค้า", item["item_key"], price, timestamp)

                        inventory[name].remove(item)

                        update_item_keys()

                        date = datetime.now().strftime("%Y-%m-%d")
                        if date in daily_profit:
                            daily_profit[date] += profit
                        else:
                            daily_profit[date] = profit

                        save_data()

                        log_message = (f"💸 **Sell Log**\nสินค้า: `{item['item_key']}`\n"
                                       f"ราคา (ซื้อ): `{buy_price}` บาท\n"
                                       f"ราคา (ขาย): `{price}` บาท\n"
                                       f"กำไร: `{profit}` บาท\n"
                                       f"ขายเมื่อ: `{timestamp}`")
                        await send_log_to_channel(bot, log_message)

                        embed = discord.Embed(
                            title="ขายสินค้า",
                            description=f"ขาย {item['item_key']} ได้ราคา {price} บาท กำไร {profit} บาท",
                            color=discord.Color.green(),
                        )
                        embed.set_footer(text=f"ขายเมื่อ {timestamp}")
                        if not interaction.response.is_done():
                            await interaction.response.send_message(embed=embed)

                        return

            embed = discord.Embed(
                title="ไม่พบสินค้า",
                description=f"ไม่พบสินค้า {unique_id} ในรายการ!",
                color=discord.Color.red(),
            )
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed)

@bot.tree.command(name="profit", description="แสดงกำไรที่ได้รับจากการขายสินค้า")
async def profit(interaction: discord.Interaction):
    timestamp = get_thailand_time()

    total_profit = sum(daily_profit.values())

    date_today = datetime.now().strftime("%Y-%m-%d")
    today_profit = daily_profit.get(date_today, 0)

    # แก้ไขการคำนวณกำไร
    profit_knight = today_profit * 0.25  # ไนท์ 25%
    profit_base = today_profit * 0.25    # เบส 25%
    profit_ex = today_profit * 0.5       # เอ็กซ์ 50%

    embed = discord.Embed(
        title="ข้อมูลกำไร",
        description=f"กำไรในวันนี้ ({date_today}): {today_profit} บาท\n"
                    f"ไนท์: {profit_knight} บาท\n"
                    f"เบส: {profit_base} บาท\n"
                    f"เอ็กซ์: {profit_ex} บาท\n"
                    f"กำไรรวมทั้งหมด: {total_profit} บาท",
        color=discord.Color.blue(),
    )
    embed.set_footer(text=f"ข้อมูลเมื่อ {timestamp}")
    if not interaction.response.is_done():
        await interaction.response.send_message(embed=embed)



@bot.tree.command(name="buy_report", description="แสดงยอดซื้อและจำนวนเงินค้างอยู่")
async def buy_report(interaction: discord.Interaction):
    timestamp = get_thailand_time()

    if not inventory:
        embed = discord.Embed(
            title="รายงานการซื้อสินค้า",
            description="ไม่มีรายการซื้อสินค้าในขณะนี้!",
            color=discord.Color.red(),
        )
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed)
        return

    table_header = ["เลข", "ชื่อ", "สถานะ", "ราคา (THB)", "ราคา (USD)"] 
    table_body = []
    total_spent = 0  

    for name, items in inventory.items():
        for item in items:
            if item.get("status") != "ขายแล้ว": 
                price_usd = item['price'] / 30 
                table_body.append([item["unique_id"], name, item["status"], item["price"], round(price_usd, 2)])

                total_spent += item['price']

    if not table_body:
        embed = discord.Embed(
            title="รายงานการซื้อสินค้า",
            description="ไม่มีสินค้าในรายการที่ยังไม่ได้ขาย!",
            color=discord.Color.red(),
        )
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed)
        return

    output = t2a(
        header=table_header,
        body=table_body,
        style=PresetStyle.plain 
    )

    embed = discord.Embed(
        title="รายงานการซื้อสินค้า",
        description=f"```\n{output}\n```",
        color=discord.Color.blue(),
    )
    embed.add_field(name="ยอดซื้อรวม", value=f"ยอดรวมที่ซื้อทั้งหมด: {total_spent} บาท", inline=False)
    embed.set_footer(text=f"ข้อมูลเมื่อ {timestamp}")

    if not interaction.response.is_done():
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="sell_report", description="แสดงยอดขายและรายการที่ขายแล้ว")
async def sell_report(interaction: discord.Interaction):
    timestamp = get_thailand_time()

    # ตรวจสอบว่ามีรายการขายใน log หรือไม่
    if not any(entry.get("action") == "ขายสินค้า" for entry in log):
        embed = discord.Embed(
            title="รายงานการขายสินค้า",
            description="ไม่มีรายการที่ถูกขายออกไป! กรุณารอการขาย!",
            color=discord.Color.red(),
        )
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed)
        return

    # สร้างตารางแสดงรายการการขาย
    table_header = ["เลข", "ชื่อ", "ราคา (ซื้อ)", "ราคา (ขาย)", "กำไร"]
    table_body = []
    total_sales = 0  # ยอดขายรวม
    total_profit = 0  # กำไรรวม

    for entry in log:
        if entry.get("action") == "ขายสินค้า":
            item_key = entry.get("item_key")
            sell_price = entry.get("price")

            for name, items in inventory.items():
                for item in items:
                    if item.get("item_key") == item_key:
                        buy_price = item["price"]
                        profit = sell_price - buy_price

                        table_body.append([
                            item["unique_id"],
                            name,
                            buy_price,
                            sell_price,
                            profit
                        ])

                        total_sales += sell_price
                        total_profit += profit

    if not table_body:
        embed = discord.Embed(
            title="รายงานการขายสินค้า",
            description="ไม่มีสินค้าในรายการที่ถูกขาย!",
            color=discord.Color.red(),
        )
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed)
        return

    # สร้างตารางด้วย table2ascii
    output = t2a(
        header=table_header,
        body=table_body,
        style=PresetStyle.plain
    )

    embed = discord.Embed(
        title="รายงานการขายสินค้า",
        description=f"```{output}```",        color=discord.Color.green(),
    )
    embed.add_field(name="ยอดขายรวม", value=f"{total_sales} บาท", inline=False)
    embed.add_field(name="กำไรรวม", value=f"{total_profit} บาท", inline=False)
    embed.set_footer(text=f"ข้อมูลเมื่อ {timestamp}")

    if not interaction.response.is_done():
        await interaction.response.send_message(embed=embed)


@bot.tree.command(name="inventory_list", description="แสดงรายการสินค้าที่มี")
async def inventory_list(interaction: discord.Interaction):
    if not inventory:
        embed = discord.Embed(
            title="รายการสินค้า",
            description="ไม่มีสินค้าในขณะนี้!",
            color=discord.Color.red(),
        )
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed)
        return


    table_header = ["เลข", "ชื่อ", "สถานะ", "ราคา (THB/USD)"] 
    table_body = []

    exchange_rate = 0.028

    for name, items in inventory.items():
        for item in items:
            price_thb = item["price"]
            price_usd = price_thb * exchange_rate
            table_body.append([
                item["unique_id"],
                name,
                item["status"],
                f"{price_thb} THB ({price_usd:.2f} USD)"
            ])

    output = t2a(
        header=table_header,
        body=table_body,
        style=PresetStyle.plain
    )

    embed = discord.Embed(
        title="รายการสินค้า",
        description=f"```\n{output}\n```",
        color=discord.Color.blue(),
    )

    if not interaction.response.is_done():
        await interaction.response.send_message(embed=embed)

bot.run(os.getenv('TOKEN'))
