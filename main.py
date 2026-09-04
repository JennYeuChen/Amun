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
        now = datetime.now()
        today = now.date()
        user_display_name = message.author.display_name
        user_avatar_url = str(
            message.author.display_name_avatar.url
            if hasattr(message.author, "display_name_avatar")
            else message.author.avatar.url
            if message.author.avatar
            else ""
        )

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
                    "last_checkin": str(today),
                    "last_checkin_at": now.isoformat(),
                    "display_name": user_display_name,
                    "avatar_url": user_avatar_url
                }
                supabase.table("sleep_tracker").insert(new_record).execute()
            else:
                data = user_data[0]
                last_checkin = datetime.strptime(data["last_checkin"], "%Y-%m-%d").date()
                last_checkin_at = data.get("last_checkin_at")

                # 舊資料沒有時間欄位時，以 last_checkin 日期的午夜作為相容預設值。
                if last_checkin_at:
                    last_checkin_time = datetime.fromisoformat(last_checkin_at.replace("Z", "+00:00")).replace(tzinfo=None)
                else:
                    last_checkin_time = datetime.combine(last_checkin, datetime.min.time())

                if now - last_checkin_time < timedelta(hours=12):
                    print("-> 12 小時內已打過卡，拒絕此次打卡 ❌")
                    await message.add_reaction("❌")
                    await bot.process_commands(message)
                    return
                elif last_checkin == today:
                    print("-> 今日已打過卡且已超過 12 小時，只更新最後打卡時間，不增加天數")
                    update_data = {
                        "last_checkin_at": now.isoformat(),
                        "display_name": user_display_name,
                        "avatar_url": user_avatar_url
                    }
                    supabase.table("sleep_tracker").update(update_data).eq("user_id", user_id).execute()
                elif last_checkin == today - timedelta(days=1):
                    print("-> 連勝 +1")
                    new_streak = data["current_streak"] + 1
                    max_streak = max(new_streak, data["max_streak"])
                    update_data = {
                        "current_streak": new_streak,
                        "max_streak": max_streak,
                        "total_days": data["total_days"] + 1,
                        "last_checkin": str(today),
                        "last_checkin_at": now.isoformat(),
                        "display_name": user_display_name,
                        "avatar_url": user_avatar_url
                    }
                    supabase.table("sleep_tracker").update(update_data).eq("user_id", user_id).execute()
                else:
                    print("-> 中斷，連勝重置為 1")
                    update_data = {
                        "current_streak": 1,
                        "total_days": data["total_days"] + 1,
                        "last_checkin": str(today),
                        "last_checkin_at": now.isoformat(),
                        "display_name": user_display_name,
                        "avatar_url": user_avatar_url
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

    # 優先讀取日期欄位，避免資料欄位缺少時造成錯誤。
    last_date = data.get("last_checkin") or data.get("last_checkin_at", "無紀錄")
    if "T" in str(last_date):
        last_date = str(last_date).split("T")[0]

    embed = discord.Embed(
        title=f"🌙 {ctx.author.display_name} 的早睡打卡名片",
        color=discord.Color.blue()
    )
    embed.add_field(name="🔥 當前連勝", value=f"`{data.get('current_streak', 0)} 天`", inline=True)
    embed.add_field(name="🏆 最高紀錄", value=f"`{data.get('max_streak', 0)} 天`", inline=True)
    embed.add_field(name="📅 總打卡數", value=f"`{data.get('total_days', 0)} 天`", inline=True)
    embed.set_footer(text=f"上次打卡日期：{last_date}")
    
    await ctx.send(embed=embed)


# --- 4. 管理員調整其他使用者數據 ---
@bot.command(name="adjust")
@commands.has_permissions(administrator=True)
async def adjust(
    ctx,
    member: discord.Member,
    current_streak: int,
    max_streak: int,
    total_days: int,
    last_checkin: str = None
):
    """用法：!adjust @使用者 當前連勝 最高連勝 總天數 [YYYY-MM-DD]"""
    try:
        update_data = {
            "current_streak": current_streak,
            "max_streak": max_streak,
            "total_days": total_days
        }

        if last_checkin:
            parsed_date = datetime.strptime(last_checkin, "%Y-%m-%d").date()
            update_data["last_checkin"] = str(parsed_date)
            update_data["last_checkin_at"] = datetime.combine(
                parsed_date, datetime.min.time()
            ).isoformat()
        else:
            update_data["last_checkin_at"] = datetime.now().isoformat()

        existing = supabase.table("sleep_tracker").select("user_id").eq(
            "user_id", str(member.id)
        ).execute()
        if not existing.data:
            await ctx.send(f"找不到 {member.mention} 的打卡資料。")
            return

        supabase.table("sleep_tracker").update(update_data).eq(
            "user_id", str(member.id)
        ).execute()

        print(f"[管理員調整] {ctx.author} 更新了 {member} 的打卡資料：{update_data}")
        await ctx.send(f"已更新 {member.mention} 的打卡資料。")
    except ValueError:
        await ctx.send("日期格式錯誤，請使用 `YYYY-MM-DD`。")
    except Exception as e:
        print(f"❌ 調整數據時發生錯誤: {e}")
        await ctx.send("調整數據失敗，請查看主機 Log。")


@adjust.error
async def adjust_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("只有管理員可以調整其他使用者的數據。")
    elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
        await ctx.send("用法：`!adjust @使用者 當前連勝 最高連勝 總天數 [YYYY-MM-DD]`")

bot.run(DISCORD_TOKEN)
