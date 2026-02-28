import discord
from discord.ext import commands
from discord import app_commands
import os

class MyCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    @app_commands.command(name="ping",description="display delay from server")
    async def ping(self,interaction:discord.Interaction):
        lag_ms=round(self.bot.latency*1000)
        await interaction.response.send_message(f'{lag_ms}ms')
    # Slash 指令：Hello
    @app_commands.command(name="hello", description="打招呼")
    async def hello(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"你好 {interaction.user.mention}!")

    # Prefix 指令：Add
    @commands.command()
    async def add(self, ctx, a: int, b: int):
        await ctx.send(a + b)

    # Slash 指令：Upload
    @app_commands.command(name="upload", description="上傳檔案並處理")
    @app_commands.describe(file="請上傳檔案")
    async def upload(self, interaction: discord.Interaction, file: discord.Attachment):
        await interaction.response.defer()
        os.makedirs("downloads", exist_ok=True)
        file_path = f"downloads/{file.filename}"
        await file.save(file_path)
        file_size = os.path.getsize(file_path)

        result_text = ""
        if file.filename.endswith(".txt"):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                result_text = f.read(100)
        else:
            result_text = "非文字檔，僅回傳大小資訊"

        await interaction.followup.send(
            f"檔案名稱: {file.filename}\n"
            f"檔案大小: {file_size/1000} KB\n"
            f"內容預覽:\n{result_text}"
        )

# Cog 的進入點
async def setup(bot):
    await bot.add_cog(MyCommands(bot))