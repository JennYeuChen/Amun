import os
from threading import Thread
from flask import Flask
import discord
from discord.ext import commands

# 1. 建立 Flask Web Server 用於 Keep-Alive
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    # Render 會自動指定 PORT 環境變數，若無則預設 8080
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# 2. 設定 Discord Bot
intents = discord.Intents.default()
intents.message_content = True  # 開啟訊息內容權限

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"機器人已成功上線：{bot.user}")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

# 3. 啟動 Web 伺服器與 Bot
if __name__ == "__main__":
    keep_alive()  # 背景啟動 Flask
    
    token = os.getenv("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("錯誤：找不到 DISCORD_TOKEN 環境變數！")