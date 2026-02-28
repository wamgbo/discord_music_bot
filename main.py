import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 在啟動時載入 cogs 資料夾下所有的 .py 檔案
@bot.event
async def on_ready():
    # 同步 Slash Commands 到 Discord
    try:
        synced = await bot.tree.sync()
        print(f"已同步 {len(synced)} 個斜線指令")
    except Exception as e:
        print(f"同步指令失敗: {e}")
        
    print(f"{bot.user} 已上線 (Hot Reload 模式)")

@bot.command()
@commands.is_owner()
async def reload(ctx):
    # 用來記錄重載成功的模組名稱
    reloaded = []
    # 用來記錄失敗的錯誤訊息
    errors = []
    # 遍歷 cogs 資料夾
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            cog_name = filename[:-3] # 移除 .py 取得檔名
            try:
                await bot.reload_extension(f'cogs.{cog_name}')
                reloaded.append(cog_name)
            except Exception as e:
                errors.append(f"{cog_name}: {e}")

    # 重載完成後同步斜線指令 (Slash Commands)
    await bot.tree.sync()

    # 回傳結果給使用者
    message = f"✅ 已成功重載: {', '.join(reloaded)}"
    if errors:
        message += f"\n❌ 重載失敗項目:\n" + "\n".join(errors)
    
    await ctx.send(message)

# 異步載入 Initial Extensions
async def main():
    async with bot:
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await bot.load_extension(f'cogs.{filename[:-3]}')
        await bot.start('--your token--')

import asyncio
if __name__ == "__main__":
    asyncio.run(main())