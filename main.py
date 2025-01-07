import discord
from discord.ext import commands
from discord import ui
from datetime import datetime
import json
import os
import pytz
from table2ascii import table2ascii as t2a, PresetStyle
from myserver import server_on

# กำหนด Intents
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True

# สร้าง Client และ CommandTree
class MyBot(discord.Client):
    def __init__(self, intents):
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)

bot = MyBot(intents)

# ไฟล์สำหรับเก็บข้อมูล
DATA_FILE = 'inventory_data.json'

# โหลดข้อมูลจากไฟล์
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
        return data.get('inventory', {}), data.get('daily_profit', {}), data.get('daily_buy', {}), data.get('log', [])
    else:
        return {}, {}, {}, []

inventory, daily_profit, daily_buy, log = load_data()

# บันทึกข้อมูลลงไฟล์
def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump({'inventory': inventory, 'daily_profit': daily_profit, 'daily_buy': daily_buy, 'log': log}, f)

# ฟังก์ชันสำหรับบันทึก log
def log_event(action, item_key, price, timestamp):
    log.append({
        "action": action,
        "item_key": item_key,
        "price": price,
        "timestamp": timestamp
    })
    save_data()

# ฟังก์ชันที่ใช้เวลาประเทศไทย (ICT)
def get_thailand_time():
    tz = pytz.timezone('Asia/Bangkok')
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.tree.sync()
    print("Commands synced!")

# ฟังก์ชันอัปเดตลำดับหน้าชื่อและ unique_id
def update_item_keys():
    global inventory
    updated_inventory = {}
    unique_id_counter = 1  # เริ่มต้นที่ 1

    for name, items in inventory.items():
        # เรียงลำดับใหม่โดยใช้ unique_id
        items.sort(key=lambda x: x["unique_id"])

        for item in items:
            item["unique_id"] = unique_id_counter  # อัปเดต unique_id ตามลำดับ
            item_key = f"{unique_id_counter}. {name}"  # แก้ไขเลขหน้าชื่อเป็น 1. 2. 3.
            item["item_key"] = item_key
            unique_id_counter += 1  # เพิ่มลำดับ unique_id

        updated_inventory[name] = items
    inventory = updated_inventory
    save_data()

# คำสั่งซื้อสินค้า
@bot.tree.command(name="buy", description="เพิ่มสินค้าเข้ารายการ")
async def buy(interaction: discord.Interaction, name: str, status: str, price: int):
    timestamp = get_thailand_time()  # ใช้เวลาประเทศไทย

    # เพิ่มสินค้าลงในรายการ
    if name not in inventory:
        inventory[name] = []

    inventory[name].append({
        "item_key": "",  # จะอัปเดตภายหลัง
        "status": status,
        "price": price,
        "unique_id": 0  # จะอัปเดตภายหลัง
    })

    # อัปเดตลำดับหน้าชื่อและ unique_id
    update_item_keys()

    # บันทึกยอดซื้อในแต่ละวัน
    date_today = datetime.now().strftime("%Y-%m-%d")
    if date_today in daily_buy:
        daily_buy[date_today] += price
    else:
        daily_buy[date_today] = price

    # บันทึกข้อมูล
    save_data()
    embed = discord.Embed(
        title="เพิ่มสินค้า",
        description=f"รับสินค้า {name} สถานะ {status} ราคา {price} บาท เข้ารายการแล้ว!",
        color=discord.Color.green(),
    )
    embed.set_footer(text=f"เพิ่มเมื่อ {timestamp}")
    if not interaction.response.is_done():
        await interaction.response.send_message(embed=embed)

# คำสั่งขายสินค้า
@bot.tree.command(name="sell", description="ขายสินค้าและคำนวณกำไร")
async def sell(interaction: discord.Interaction, unique_id: int, price: int):
    timestamp = get_thailand_time()  # ใช้เวลาประเทศไทย

    for name, items in inventory.items():
        for item in items:
            if item["unique_id"] == unique_id:
                buy_price = item["price"]

                # ขายสินค้า
                profit = price - buy_price  # คำนวณกำไร

                # Log event
                log_event("ขายสินค้า", item["item_key"], price, timestamp)

                # ลบสินค้าจากรายการหลังการขาย
                inventory[name].remove(item)

                # อัปเดตคีย์ลัดทันทีหลังการขาย
                update_item_keys()  # อัปเดตคีย์ลัดสินค้า

                # บันทึกกำไรในแต่ละวัน
                date = datetime.now().strftime("%Y-%m-%d")
                if date in daily_profit:
                    daily_profit[date] += profit
                else:
                    daily_profit[date] = profit

                # บันทึกข้อมูล
                save_data()

                # แสดงข้อมูลกำไรในการขาย
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

# คำสั่งเช็คกำไร
@bot.tree.command(name="profit", description="แสดงกำไรที่ได้รับจากการขายสินค้า")
async def profit(interaction: discord.Interaction):
    timestamp = get_thailand_time()  # ใช้เวลาประเทศไทย

    # คำนวณกำไรรวมจากทุกวัน
    total_profit = sum(daily_profit.values())

    # กำไรในวันนี้
    date_today = datetime.now().strftime("%Y-%m-%d")
    today_profit = daily_profit.get(date_today, 0)

    # คำนวณการแบ่งกำไร
    profit_arm = today_profit * 0.7  # 30% ของพี่อาร์ม 
    profit_ex = today_profit * 0.3  # 70% ของเอ็ก 

    embed = discord.Embed(
        title="ข้อมูลกำไร",
        description=f"กำไรในวันนี้ ({date_today}): {today_profit} บาท\n"
                    f"พี่อาร์ม: {profit_arm} บาท\n"
                    f"เอ็ก: {profit_ex} บาท\n"
                    f"กำไรรวมทั้งหมด: {total_profit} บาท",
        color=discord.Color.blue(),
    )
    embed.set_footer(text=f"ข้อมูลเมื่อ {timestamp}")
    if not interaction.response.is_done():
        await interaction.response.send_message(embed=embed)
# คำสั่งเพิ่ม /wallet
@bot.tree.command(name="wallet", description="แสดงกระเป๋าสตางค์")
async def wallet(interaction: discord.Interaction):
    wallet_address = "LS1TSgMNapSBSrpadKPDnWn4MuwcLRf5dp"
    timestamp = get_thailand_time()

    embed = discord.Embed(
        title="กระเป๋าสตางค์",
        description=f"ที่อยู่กระเป๋า: `{wallet_address}`",
        color=discord.Color.blue(),
    )
    embed.set_footer(text=f"ข้อมูลเมื่อ {timestamp}")

    if not interaction.response.is_done():
        await interaction.response.send_message(embed=embed)

# Remaining code continues unchanged.

# คำสั่งแสดงรายงานการซื้อสินค้า
@bot.tree.command(name="buy_report", description="แสดงรายงานการซื้อสินค้า")
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

    embed = discord.Embed(title="รายงานการซื้อสินค้า", color=discord.Color.blue())
    total_spent = 0
    for name, items in inventory.items():
        for item in items:
            embed.add_field(name=f"{item['item_key']} {item['status']}", value=f"ราคา: {item['price']} บาท", inline=False)
            total_spent += item['price']

    embed.add_field(name="รวมทั้งหมด", value=f"ยอดซื้อรวม: {total_spent} บาท", inline=False)
    embed.set_footer(text=f"ข้อมูลเมื่อ {timestamp}")
    if not interaction.response.is_done():
        await interaction.response.send_message(embed=embed)

# คำสั่งแสดงรายการสินค้าที่มี
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

    # สร้างตารางแสดงรายการสินค้าด้วย table2ascii
    table_header = ["เลข", "ชื่อ", "สถานะ"]  # ลบคอลัมน์ ไอเท็มคีย์
    table_body = []

    # เตรียมข้อมูลเพื่อแสดงในตาราง
    for name, items in inventory.items():
        for item in items:
            table_body.append([item["unique_id"], name, item["status"]])  # ลบไอเท็มคีย์

    # สร้างตาราง โดยเลือก style ที่ไม่มีขอบ
    output = t2a(
        header=table_header,
        body=table_body,
        style=PresetStyle.plain  # ใช้ style ที่ไม่มีขอบ
    )

    embed = discord.Embed(
        title="รายการสินค้า",
        description=f"```\n{output}\n```",
        color=discord.Color.blue(),
    )
    
    if not interaction.response.is_done():
        await interaction.response.send_message(embed=embed)


server_on()

bot.run('TOKEN')
