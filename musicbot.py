import discord
from discord.ext import commands
import yt_dlp
import asyncio
import math
import random
import os
from datetime import datetime

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

client = commands.Bot(command_prefix='!', intents=intents)

FFMPEG_OPTIONS = {'options': '-vn', 'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'}
YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist': True}
ITEMS_PER_PAGE = 10
RADIO_FILE_FOLDER = r"MP3 FILE FOLDER" #Put the directory of the folder with all the .mp3 files you want to play organized in subfolders

def get_radio_file(path):
    dirs = [os.path.join(path, d) for d in os.listdir(path) 
            if os.path.isdir(os.path.join(path, d))]

    chosen_dir = random.choice(dirs)

    files = [os.path.join(chosen_dir, f) for f in os.listdir(chosen_dir) #If you just want to have all the .mp3 files in a single folder remove all the previous code from this function and replace chosen_dir with path
            if os.path.isfile(os.path.join(chosen_dir, f))]

    return random.choice(files)


class MusicBot(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.queue = []
        self.current_song = None
        self.start_time = None
        self.disconnect_task = None
        self.search_results = {}  # Store search results for each user
        self.last_np_message = None
        self.radio_mode = False

    @client.event
    async def on_ready():
        print(f'Logged in as {client.user} (ID: {client.user.id})')

    @commands.command(name="radio-mode", aliases=['rm'])
    async def toggle_radio_mode(self, ctx):
        self.radio_mode = not self.radio_mode
        status = "enabled" if self.radio_mode else "disabled"
        await ctx.send(f":radio: Radio mode {status}!")

    @commands.command()
    async def search(self, ctx, *, query):
        async with ctx.typing():
            try:
                with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                    info = ydl.extract_info(f"ytsearch10:{query}", download=False)
                    if not info['entries']:
                        return await ctx.send("No results found!")
                    
                    # Store the search results for this user
                    self.search_results[ctx.author.id] = info['entries']
                    
                    # Create embed with search results
                    embed = discord.Embed(
                        title=":mag_right: Search Results",
                        description="Type the number of the song you want to play (1-10)\nType 'cancel' to cancel the selection",
                        color=discord.Color.blue()
                    )
                    
                    # Add each result to the embed
                    for i, entry in enumerate(info['entries'], 1):
                        duration = str(int(entry.get('duration', 0) // 60)) + ':' + str(int(entry.get('duration', 0) % 60)).zfill(2)
                        embed.add_field(
                            name=f"{i}. {entry['title']}",
                            value=f"Duration: {duration}",
                            inline=False
                        )
                    
                    await ctx.send(embed=embed)
                    
                    # Wait for user response
                    def check(m):
                        return m.author == ctx.author and m.channel == ctx.channel and \
                               (m.content.isdigit() or m.content.lower() == 'cancel')
                    
                    try:
                        msg = await self.client.wait_for('message', timeout=30.0, check=check)
                    except asyncio.TimeoutError:
                        del self.search_results[ctx.author.id]
                        return await ctx.send(":alarm_clock: Search timed out!")
                    
                    if msg.content.lower() == 'cancel':
                        del self.search_results[ctx.author.id]
                        return await ctx.send(":no_entry_sign: Search cancelled!")
                    
                    # Process the selection
                    selection = int(msg.content)
                    if not 1 <= selection <= len(info['entries']):
                        del self.search_results[ctx.author.id]
                        return await ctx.send(":no_entry_sign: Invalid selection!")
                    
                    selected_song = info['entries'][selection-1]
                    
                    # Add the selected song to the queue
                    voice_channel = ctx.author.voice.channel if ctx.author.voice else None
                    if not voice_channel:
                        del self.search_results[ctx.author.id]
                        return await ctx.send(":no_entry_sign: You must be listening in a voice channel to use that!")
                    
                    if not ctx.voice_client:
                        await voice_channel.connect()
                    
                    # Cancel any existing disconnect task
                    if self.disconnect_task:
                        self.disconnect_task.cancel()
                        self.disconnect_task = None
                    
                    # Add song to queue
                    duration = selected_song.get('duration', 0)
                    length = f"{int(duration // 60)}:{str(int(duration % 60)).zfill(2)}"
                    self.queue.append({
                        'url': selected_song['url'],
                        'title': selected_song['title'],
                        'duration': duration
                    })
                    await ctx.send(f':notes: Added **{selected_song["title"]}** (`{length}`) to begin playing')
                    
                    if not ctx.voice_client.is_playing():
                        await self.play_next(ctx)
                    
            except Exception as e:
                await ctx.send(f":no_entry_sign: An error occurred: {str(e)}")
            finally:
                # Clean up search results
                if ctx.author.id in self.search_results:
                    del self.search_results[ctx.author.id]

    @commands.command(aliases=['p'])
    async def play(self, ctx, *, search):
        voice_channel = ctx.author.voice.channel if ctx.author.voice else None
        if not voice_channel:
            return await ctx.send(":no_entry_sign: You must be listening in a voice channel to use that!")
        if not ctx.voice_client:
            await voice_channel.connect()
        
        # Cancel any existing disconnect task
        if self.disconnect_task:
            self.disconnect_task.cancel()
            self.disconnect_task = None

        async with ctx.typing():
            try:
                with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                    try:
                        info = ydl.extract_info(f"ytsearch:{search}", download=False)
                        if 'entries' in info and not info['entries']:
                            return await ctx.send(":cross_mark: Couldn't find that song. Try using a direct link or !search for better results!")
                        if 'entries' in info:
                            info = info['entries'][0]
                        url = info['url']
                        title = info['title']
                        duration = info.get('duration', 0)
                        length = str(int(duration // 60)) + ':' + str(int(duration % 60)).zfill(2)
                        self.queue.append({'url': url, 'title': title, 'duration': duration})
                        await ctx.send(f':notes: Added **{title}** (`{length}`) to begin playing')
                    except:
                        await ctx.send(f":cross_mark: Couldn't find that song. Try using a direct link or !search for better results!")
            except Exception as e:
                await ctx.send(f":cross_mark: An error occurred: {str(e)}\nTry using a direct link or !search instead!")
        if not ctx.voice_client.is_playing():
            await self.play_next(ctx)

    async def play_radio(self, ctx):
        ctx.voice_client.play(discord.FFmpegPCMAudio(executable=r"C:\Program Files (x86)\FFmpeg\bin\ffmpeg.exe", source=get_radio_file(RADIO_FILE_FOLDER)))

    async def play_next(self, ctx):
        
        if self.last_np_message:
            try:
                await self.last_np_message.delete()
            except:
                pass
        
        if self.queue:
            if self.radio_mode and random.random() < 0.5:
                await self.play_radio(ctx)
                while ctx.voice_client.is_playing():
                    await asyncio.sleep(1)

            song = self.queue.pop(0)
            self.current_song = song
            self.start_time = datetime.now()
            source = await discord.FFmpegOpusAudio.from_probe(song['url'], **FFMPEG_OPTIONS)
            ctx.voice_client.play(source, after=lambda _: self.client.loop.create_task(self.play_next(ctx)))

            activity = discord.Activity(
                type=discord.ActivityType.listening,
                name=song['title'][:128]
            )
            await self.client.change_presence(activity=activity)

            self.last_np_message = await ctx.send(f':arrow_forward: Now playing **{song["title"]}**')
        else:
            self.current_song = None
            self.start_time = None
            # Schedule disconnect after 3 minutes
            await self.client.change_presence(activity=None)
            self.disconnect_task = self.client.loop.create_task(self.disconnect_after_timeout(ctx))

    async def disconnect_after_timeout(self, ctx):
        await asyncio.sleep(180)  # Wait 3 minutes
        if not self.queue and not ctx.voice_client.is_playing():
            await ctx.voice_client.disconnect()
            await ctx.send(":hourglass: Disconnected due to inactivity.")

    @commands.command(aliases=['q'])
    async def queue(self, ctx, page: int = 1):
        if not self.current_song and not self.queue:
            return await ctx.send(":stop_button: No songs in queue!")

        # Calculate total pages
        total_pages = math.ceil(len(self.queue) / ITEMS_PER_PAGE)
        page = min(max(1, page), max(1, total_pages))
        
        embed = discord.Embed(title=":musical_note: Music Queue", color=discord.Color.blue())
        
        # Add currently playing song
        if self.current_song:
            duration = str(int(self.current_song['duration'] // 60)) + ':' + str(int(self.current_song['duration'] % 60)).zfill(2)
            embed.add_field(
                name=":arrow_forward: Currently Playing:",
                value=f"**{self.current_song['title']}** `{duration}`",
                inline=False
            )

        # Add queued songs
        start_idx = (page - 1) * ITEMS_PER_PAGE
        end_idx = min(start_idx + ITEMS_PER_PAGE, len(self.queue))
        
        if self.queue:
            queue_list = []
            for i in range(start_idx, end_idx):
                song = self.queue[i]
                duration = str(int(song['duration'] // 60)) + ':' + str(int(song['duration'] % 60)).zfill(2)
                queue_list.append(f"{i+1}. **{song['title']}** `{duration}`")
            
            embed.add_field(
                name="Up Next:",
                value="\n".join(queue_list) if queue_list else "No songs in queue",
                inline=False
            )
            
            embed.set_footer(text=f"Page {page}/{total_pages}")
        
        await ctx.send(embed=embed)

    @commands.command(name="now-playing", aliases=['np'])
    async def now_playing(self, ctx):
        if not self.current_song or not ctx.voice_client.is_playing():
            return await ctx.send("Nothing is playing right now!")
        
        current_time = datetime.now()
        elapsed_time = (current_time - self.start_time).total_seconds()
        total_duration = self.current_song['duration']
        
        # Format times as MM:SS
        elapsed_str = f"{int(elapsed_time // 60)}:{str(int(elapsed_time % 60)).zfill(2)}"
        total_str = f"{int(total_duration // 60)}:{str(int(total_duration % 60)).zfill(2)}"
        
        embed = discord.Embed(title=":arrow_forward: Now Playing", color=discord.Color.green())
        embed.add_field(
            name=self.current_song['title'],
            value=f"Time: {elapsed_str}/{total_str}",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @commands.command(aliases=['st'])
    async def stop(self, ctx):
        if ctx.voice_client:
            self.queue.clear()
            self.current_song = None
            self.start_time = None
            if self.disconnect_task:
                self.disconnect_task.cancel()
                self.disconnect_task = None
            ctx.voice_client.stop()
            await ctx.voice_client.disconnect()
            await self.client.change_presence(activity=None)
            await ctx.send(":stop_sign: Stopped playing, cleared queue, and disconnected from voice channel.")

    @commands.command(aliases=['s','sk'])
    async def skip(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send(":track_next: Skipped!")

async def main():
    await client.add_cog(MusicBot(client))
    await client.start('BOT TOKEN HERE') #Put your bot's token here

asyncio.run(main())
