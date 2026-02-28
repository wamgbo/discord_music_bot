import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import asyncio
import os

# ======== 圖形化控制按鈕介面 ========
class MusicControlView(discord.ui.View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id

    @discord.ui.button(label="暫停/繼續", style=discord.ButtonStyle.blurple, emoji="⏯️")
    async def toggle_play(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc: return
        if vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ 已暫停", ephemeral=True)
        elif vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ 繼續播放", ephemeral=True)

    @discord.ui.button(label="單曲循環: 關閉", style=discord.ButtonStyle.gray, emoji="🔂")
    async def toggle_loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_state = self.cog.loop_status.get(self.guild_id, False)
        new_state = not current_state
        self.cog.loop_status[self.guild_id] = new_state

        button.label = f"單曲循環: {'開啟' if new_state else '關閉'}"
        button.style = discord.ButtonStyle.success if new_state else discord.ButtonStyle.gray
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="下一首", style=discord.ButtonStyle.green, emoji="⏭️")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc:
            self.cog.loop_status[self.guild_id] = False # 跳過時自動關閉循環
            vc.stop()
            await interaction.response.send_message("⏭️ 已跳過歌曲", ephemeral=True)

    @discord.ui.button(label="停止", style=discord.ButtonStyle.red, emoji="⏹️")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc:
            self.cog.music_queue[self.guild_id] = []
            self.cog.loop_status[self.guild_id] = False
            vc.stop()
            await interaction.response.send_message("⏹️ 已停止並清空清單", ephemeral=True)

# ======== 音樂指令核心類別 ========
class MusicCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.music_queue = {}    # {guild_id: [song_info_list]}
        self.loop_status = {}    # {guild_id: bool}
        self.current_song = {}   # {guild_id: song_info}

    def get_queue(self, guild_id):
        if guild_id not in self.music_queue:
            self.music_queue[guild_id] = []
        return self.music_queue[guild_id]

    async def download_bili(self, url):
        """專為 Bilibili 設計的下載轉碼邏輯"""
        os.makedirs("downloads", exist_ok=True)
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'downloads/%(id)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
            return ydl.prepare_filename(info).rsplit('.', 1)[0] + ".mp3"

    async def play_next(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        vc = interaction.guild.voice_client
        if not vc: return

        # 判斷是否需要單曲循環
        is_looping = self.loop_status.get(guild_id, False)
        
        if is_looping and guild_id in self.current_song:
            song = self.current_song[guild_id]
        else:
            queue = self.get_queue(guild_id)
            if not queue:
                self.current_song.pop(guild_id, None)
                return await interaction.channel.send("✨ 所有歌曲已播放完畢。")
            song = queue.pop(0)
            self.current_song[guild_id] = song

        url = song['url']
        is_bili = "bilibili.com" in url or "b23.tv" in url
        
        try:
            if is_bili:
                # Bilibili: 下載後播放
                file_path = await self.download_bili(url)
                source = discord.FFmpegPCMAudio(file_path)
                
                def after_playing(e):
                    # 如果沒開啟循環，播完就刪除檔案
                    if not self.loop_status.get(guild_id, False):
                        if os.path.exists(file_path): os.remove(file_path)
                    asyncio.run_coroutine_threadsafe(self.play_next(interaction), self.bot.loop)
            else:
                # YouTube: 直接串流播放
                headers = f"Referer: {url}\r\nUser-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36\r\n"
                ffmpeg_opts = {
                    'before_options': (
                        f'-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 '
                        f'-headers "{headers}"'
                    ),
                    'options': (
                        '-vn '                # 停用影片
                        # '-b:a 128k '          # 強制設定音訊位元率，避免跳動
                        # '-bufsize 512k '      # 設定緩衝區大小
                        # '-probesize 10M '     # 增加解析數據量，提高穩定性
                        # '-analyzeduration 10M' 
                    ),
                }
                source = await discord.FFmpegOpusAudio.from_probe(song['stream_url'], **ffmpeg_opts)
                after_playing = lambda e: asyncio.run_coroutine_threadsafe(self.play_next(interaction), self.bot.loop)

            vc.play(source, after=after_playing)
            
            view = MusicControlView(self, guild_id)
            # status_prefix = "🔂 [循環中]" if is_looping else "🎶 [正在播放]"
            # await interaction.channel.send(f"{status_prefix} **{song['title']}**", view=view)

        except Exception as e:
            await interaction.channel.send(f"❌ 播放失敗: {e}")
            asyncio.run_coroutine_threadsafe(self.play_next(interaction), self.bot.loop)

    @app_commands.command(name="play", description="播放音樂 (支援 YT 串流與 Bili 下載)")
    async def play(self, interaction: discord.Interaction, url: str):
        if not interaction.user.voice:
            return await interaction.response.send_message("❌ 你必須先加入語音頻道！", ephemeral=True)

        await interaction.response.defer()

        # 解析網址資訊
        ydl_opts = {'format': 'bestaudio/best', 'quiet': True, 'noplaylist': True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                loop = asyncio.get_event_loop()
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
                song_data = {
                    'url': url,
                    'stream_url': info.get('url'),
                    'title': info.get('title', '未知歌曲'),
                }
        except Exception as e:
            return await interaction.followup.send(f"❌ 無法解析網址: {e}")

        # 加入清單
        queue = self.get_queue(interaction.guild.id)
        queue.append(song_data)

        # 處理語音連接
        vc = interaction.guild.voice_client
        if not vc:
            vc = await interaction.user.voice.channel.connect()

        if not vc.is_playing() and not vc.is_paused():
            await interaction.followup.send(f"✅ 開始播放：{song_data['title']}")
            await self.play_next(interaction)
        else:
            await interaction.followup.send(f"⌛ 已加入清單：{song_data['title']} (排第 {len(queue)} 位)")

    @app_commands.command(name="list", description="顯示播放清單")
    async def list_queue(self, interaction: discord.Interaction):
        queue = self.get_queue(interaction.guild.id)
        if not queue:
            return await interaction.response.send_message("目前播放清單是空的。")
        
        embed = discord.Embed(title="🎶 當前播放清單", color=discord.Color.blue())
        desc = ""
        for i, song in enumerate(queue[:10], 1):
            desc += f"**{i}.** {song['title']}\n"
        
        if len(queue) > 10:
            desc += f"\n*...以及其他 {len(queue)-10} 首歌*"
            
        embed.description = desc
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(MusicCommands(bot))