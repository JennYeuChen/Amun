import os
import re
from datetime import datetime, timedelta
import discord
from discord.ext import commands
from supabase import create_client, Client

# --- 1. 設定 Discord 與 Supabase 憑證 ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# 指定目標打卡頻道 ID
TARGET_CHANNEL_ID = 1527023446444478546

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"機器人已成功上線：{bot.user}")

# --- 2. 自動監聽訊息與系統日期判定 ---
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # 限定只在指定的打卡頻道觸發
    if message.channel.id != TARGET_CHANNEL_ID:
        await bot.process_commands(message)
        return

    # 正則表達式：支援阿拉伯數字與中文數字
    pattern = r"(第\s*(\d+|[一二三四五六七八九十百]+)\s*天|Day\s*\d+)"
    if re.search(pattern, message.content, re.IGNORECASE):
        print(f"[{datetime.now()}] 收到打卡訊息：{message.content} (來自: {message.author})")

        user_id = str(message.author.id)
        today = datetime.now().date()

        try:
            # 查詢使用者資料
            res = supabase.table("sleep_tracker").select("*").eq("user_id", user_id).execute()
            user_data = res.data

            if not user_data:
                print("-> 新使用者打卡")
                new_record = {
                    "user_id": user_id,
                    "current_streak": 1,
                    "max_streak": 1,
                    "total_days": 1,
                    "last_checkin": str(today)
                }
                supabase.table("sleep_tracker").insert(new_record).execute()
            else:
                data = user_data[0]
                last_checkin = datetime.strptime(data["last_checkin"], "%Y-%m-%d").date()

                if last_checkin == today:
                    print("-> 今天已打過卡 (更新時間並給予反應測試)")
                elif last_checkin == today - timedelta(days=1):
                    print("-> 連勝 +1")
                    new_streak = data["current_streak"] + 1
                    max_streak = max(new_streak, data["max_streak"])
                    update_data = {
                        "current_streak": new_streak,
                        "max_streak": max_streak,
                        "total_days": data["total_days"] + 1,
                        "last_checkin": str(today)
                    }
                    supabase.table("sleep_tracker").update(update_data).eq("user_id", user_id).execute()
                else:
                    print("-> 中斷，連勝重置為 1")
                    update_data = {
                        "current_streak": 1,
                        "total_days": data["total_days"] + 1,
                        "last_checkin": str(today)
                    }
                    supabase.table("sleep_tracker").update(update_data).eq("user_id", user_id).execute()

            # 無論情況如何，只要符合格式就一定點擊 ✅
            await message.add_reaction("✅")
            print("-> 成功按讚 ✅")

        except Exception as e:
            print(f"❌ 發生錯誤: {e}")

    # 確保其他指令能正常運作
    await bot.process_commands(message)

# --- 3. 個人名片指令 !profile 或 /profile ---
@bot.command(name="profile")
async def profile(ctx):
    user_id = str(ctx.author.id)
    res = supabase.table("sleep_tracker").select("*").eq("user_id", user_id).execute()
    
    if not res.data:
        await ctx.send("你還沒有任何打卡紀錄喔！在指定頻道發送「第一天」即可開始打卡。")
        return
        
    data = res.data[0]
    
    embed = discord.Embed(
        title=f"🌙 {ctx.author.display_name} 的早睡打卡名片",
        color=discord.Color.blue()
    )
    embed.add_field(name="🔥 當前連勝", value=f"`{data['current_streak']} 天`", inline=True)
    embed.add_field(name="🏆 最高紀錄", value=f"`{data['max_streak']} 天`", inline=True)
    embed.add_field(name="📅 總打卡數", value=f"`{data['total_days']} 天`", inline=True)
    embed.set_footer(text=f"上次打卡日期：{data['last_checkin']}")
    
    await ctx.send(embed=embed)

bot.run(DISCORD_TOKEN)
