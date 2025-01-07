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
ALLOWED_USERS = [852854008602820626, 810222269577953343]
    
class MyBot(discord.Client):
    def __init__(self, intents):
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)

bot = MyBot(intents)

DATA_FILE = 'inventory_data.json'


def load_inventory_data_2():
            try:
                with open('inventory_data_2.json', 'r') as file:
                    return json.load(file)
            except FileNotFoundError:
                return {"daily_rbprofit": {}}

        # ฟังก์ชันสำหรับบันทึกข้อมูลไปยังไฟล์ JSON
def save_inventory_data_2(data):
            with open('inventory_data_2.json', 'w') as file:
                json.dump(data, file, indent=4)

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

    profit_arm = today_profit * 0.7
    profit_ex = today_profit * 0.3  

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

# คำนวณกำไรจากการขาย Robux
        # คำนวณกำไรจากการขาย Robux
@bot.tree.command(name="rbbuy", description="รับ Robux และคำนวณกำไรจาก Robux")
async def rbbuy(interaction: discord.Interaction, amount: int, rate: float):
                    if not is_user_allowed(interaction):
                        await interaction.response.send_message("คุณไม่มีสิทธิ์ใช้คำสั่งนี้!", ephemeral=True)
                        return

                    timestamp = get_thailand_time()

                    # คำนวณกำไรจากการรับ Robux
                    rbprofit = amount / rate

                    # โหลดข้อมูลจากไฟล์ JSON สำหรับ Robux
                    data_2 = load_inventory_data_2()

                    # ตรวจสอบว่ามี 'daily_rbprofit' หรือไม่ หากไม่มีให้สร้าง
                    if "daily_rbprofit" not in data_2:
                        data_2["daily_rbprofit"] = {}

                    # เพิ่มหรืออัพเดตกำไรจากการขาย Robux
                    date_today = datetime.now().strftime("%Y-%m-%d")
                    if date_today in data_2["daily_rbprofit"]:
                        data_2["daily_rbprofit"][date_today] += rbprofit
                    else:
                        data_2["daily_rbprofit"][date_today] = rbprofit

                    # Update the Robux balance
                    if "robux_balance" not in data_2:
                        data_2["robux_balance"] = 0  # Initial balance if not present
                    data_2["robux_balance"] += amount  # Add received Robux to balance

                    # บันทึกข้อมูลกลับลงไฟล์ JSON
                    save_inventory_data_2(data_2)

                    # บันทึกข้อมูลการรับ
                    log_event("รับ Robux", f"รับ {amount} Robux เรท {rate}", rbprofit, timestamp)

                    log_message = f"🎮 **รับ Robux**\nจำนวน: `{amount} Robux`\nเรท: `{rate}`\nในราคา: `{rbprofit}` บาท\nรับเมื่อ: `{timestamp}`"
                    await send_log_to_channel(bot, log_message)

                    embed = discord.Embed(
                        title="รับ Robux",
                        description=f"รับ {amount} Robux ที่เรท {rate} ราคา {rbprofit} บาท!",
                        color=discord.Color.green(),
                    )
                    embed.set_footer(text=f"รับเมื่อ {timestamp}")
                    if not interaction.response.is_done():
                        await interaction.response.send_message(embed=embed)



@bot.tree.command(name="rbprofit", description="แสดงกำไรจากการขาย Robux")
async def rbprofit(interaction: discord.Interaction):
            timestamp = get_thailand_time()

            # โหลดข้อมูลจากไฟล์ JSON สำหรับ Robux
            data_2 = load_inventory_data_2()

            # ตรวจสอบว่ามี 'daily_rbprofit' หรือไม่ หากไม่มีให้สร้าง
            if "daily_rbprofit" not in data_2:
                data_2["daily_rbprofit"] = {}

            total_rbprofit = sum(data_2["daily_rbprofit"].values())

            date_today = datetime.now().strftime("%Y-%m-%d")
            today_rbprofit = data_2["daily_rbprofit"].get(date_today, 0)

            embed = discord.Embed(
                title="ข้อมูลกำไรจากการขาย Robux",
                description=f"กำไรจากการขาย Robux ในวันนี้ ({date_today}): {today_rbprofit} บาท\n"
                            f"กำไรรวมทั้งหมดจากการขาย Robux: {total_rbprofit} บาท",
                color=discord.Color.blue(),
            )
            embed.set_footer(text=f"ข้อมูลเมื่อ {timestamp}")
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed)

@bot.tree.command(name="rbsell", description="ขาย Robux และคำนวณกำไรจาก Robux")
async def rbsell(interaction: discord.Interaction, amount: int, rate: float):
                    if not is_user_allowed(interaction):
                        await interaction.response.send_message("คุณไม่มีสิทธิ์ใช้คำสั่งนี้!", ephemeral=True)
                        return

                    timestamp = get_thailand_time()

                    # Assuming you have a record of buy rates, retrieve the relevant buy rate (this should be implemented).
                    buy_rate = 50  # Replace with the actual buy rate retrieval logic
                    if rate < buy_rate:
                        loss = (buy_rate - rate) * amount
                        profit_message = f"ขาดทุน: -{loss} บาท"
                    else:
                        profit = (rate - buy_rate) * amount
                        profit_message = f"กำไร: {profit} บาท"

                        profit = amount * rate

                        log_event("ขาย Robux", f"ขาย {amount} Robux ที่เรท {rate}", profit, timestamp)

                    log_message = f"💸 **ขาย Robux**\nจำนวน: `{amount} Robux`\nเรท: `{rate}`\n{profit_message}\nขายเมื่อ: `{timestamp}`"
                    await send_log_to_channel(bot, log_message)

                    embed = discord.Embed(
                        title="ขาย Robux",
                        description=f"ขาย {amount} Robux ที่เรท {rate} {profit_message}",
                        color=discord.Color.green(),
                    )
                    embed.set_footer(text=f"ขายเมื่อ {timestamp}")
                    if not interaction.response.is_done():
                        await interaction.response.send_message(embed=embed)

# คำนวณจำนวน Robux ที่มีในสต็อก
@bot.tree.command(name="rbstock", description="แสดงยอด Robux ที่เหลือ")
async def rbstock(interaction: discord.Interaction):
            timestamp = get_thailand_time()

            # โหลดข้อมูลจากไฟล์ JSON สำหรับ Robux
            data_2 = load_inventory_data_2()

            # ตรวจสอบว่ามี 'robux_balance' หรือไม่
            if "robux_balance" not in data_2:
                data_2["robux_balance"] = 0  # If no balance exists, initialize it.

            remaining_rb = data_2["robux_balance"]

            embed = discord.Embed(
                title="ยอด Robux ที่เหลือ",
                description=f"ยอด Robux ที่เหลือ: `{remaining_rb}`",
                color=discord.Color.blue(),
            )
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

bot.run('')
