import asyncio
import os
import re
import json
import glob
import random
import logging
from typing import Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

# --- EXTERNAL DEPENDENCIES (MOCK/PLACEHOLDERS) ---
# NOTE: The actual definitions for these must exist in your project's utils folder.
def is_on_off(status_id):
    """MOCK: Placeholder for database check (e.g., streaming status)."""
    return True

def time_to_seconds(duration_min):
    """MOCK: Placeholder for time conversion."""
    if duration_min:
        try:
            # Simple conversion for MM:SS
            parts = duration_min.split(':')
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
        except:
            return 0
    return 0
# --- END MOCK ---

# --- UTILITY FUNCTIONS ---

def cookie_txt_file():
    """Selects a random .txt file from the 'cookies' folder for yt-dlp."""
    folder_path = f"{os.getcwd()}/cookies"
    filename = f"{os.getcwd()}/cookies/logs.csv"
    txt_files = glob.glob(os.path.join(folder_path, '*.txt'))
    
    # Using try-except for robust file handling
    try:
        if not txt_files:
            logging.warning("No .txt files found in the specified cookies folder.")
            return ""
        
        cookie_txt_file = random.choice(txt_files)
        
        # Log the chosen file path (ensure the directory exists)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'a') as file:
            file.write(f'Choosen File : {cookie_txt_file}\n')
            
        return f"""cookies/{str(cookie_txt_file).split("/")[-1]}"""
    except Exception as e:
        logging.error(f"Error in cookie_txt_file: {e}")
        return ""


async def check_file_size(link):
    """Checks the total file size of the streamable formats for a link."""
    async def get_format_info(link):
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_txt_file(),
            "-J",
            link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            print(f'Error:\n{stderr.decode()}')
            return None
        return json.loads(stdout.decode())

    def parse_size(formats):
        total_size = 0
        for format in formats:
            # Use get for safety
            total_size += format.get('filesize') or 0
        return total_size

    info = await get_format_info(link)
    if info is None:
        return None
    
    formats = info.get('formats', [])
    if not formats:
        print("No formats found.")
        return None
    
    total_size = parse_size(formats)
    return total_size

async def shell_cmd(cmd):
    """Executes a non-blocking shell command."""
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    error_str = errorz.decode("utf-8")
    
    if errorz:
        if "unavailable videos are hidden" in error_str.lower():
            return out.decode("utf-8")
        else:
            return error_str
    return out.decode("utf-8")


# --- YOUTUBE API CLASS ---

class YouTubeAPI:
    """Utility class for fetching YouTube metadata and streaming URLs."""
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if re.search(self.regex, link):
            return True
        else:
            return False

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            # Check entities in message text
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            # Check entities in message caption
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        if offset in (None,):
            return None
        return text[offset : offset + length]

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0
        return title, duration_min, duration_sec, thumbnail, vidid

    # --- Methods for specific details (title, duration, thumbnail, track, formats, slider) are omitted for space, 
    #     as they are repetitive queries using VideosSearch or yt-dlp - kept in the original format ---
    
    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
        return title

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            duration = result["duration"]
        return duration

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        return thumbnail

    async def video(self, link: str, videoid: Union[bool, str] = None):
        """Returns the direct stream URL (G-flag) for playback."""
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        
        # Uses -g flag to return the stream URL without downloading
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies",cookie_txt_file(),
            "-g",
            "-f",
            "best[height<=?720][width<=?1280]",
            f"{link}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if stdout:
            return 1, stdout.decode().split("\n")[0]
        else:
            return 0, stderr.decode()

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        
        # Uses shell_cmd to get playlist IDs
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_txt_file()} --playlist-end {limit} --skip-download {link}"
        )
        try:
            result = playlist.split("\n")
            # Cleanup empty strings from the list
            result = [key for key in result if key]
        except:
            result = []
        return result

    # --- Rest of the helper methods are omitted for brevity, keeping only 'download' ---

    async def download(
        self,
        link: str,
        mystic, # Pyrogram message object for updates
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        """Handles conditional downloading or falls back to stream URL retrieval."""
        if videoid:
            link = self.base + link
        loop = asyncio.get_running_loop()
        
        # --- Internal Download Definitions (Kept original logic) ---
        def audio_dl():
            ydl_optssx = {
                "format": "bestaudio/best", "outtmpl": "downloads/%(id)s.%(ext)s", "quiet": True, 
                "cookiefile" : cookie_txt_file(), "no_warnings": True, "geo_bypass": True, "nocheckcertificate": True
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, False)
            xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
            if not os.path.exists(xyz): x.download([link])
            return xyz

        def video_dl():
            ydl_optssx = {
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                "outtmpl": "downloads/%(id)s.%(ext)s", "quiet": True, 
                "cookiefile" : cookie_txt_file(), "no_warnings": True, "geo_bypass": True, "nocheckcertificate": True
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, False)
            xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
            if not os.path.exists(xyz): x.download([link])
            return xyz

        def song_video_dl():
            # Logic for format-specific download
            formats = f"{format_id}+140"
            fpath = f"downloads/{title}"
            ydl_optssx = {
                "format": formats, "outtmpl": fpath, "quiet": True, "no_warnings": True,
                "cookiefile" : cookie_txt_file(), "prefer_ffmpeg": True, "merge_output_format": "mp4",
                "geo_bypass": True, "nocheckcertificate": True,
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])

        def song_audio_dl():
            # Logic for format-specific audio download and conversion
            fpath = f"downloads/{title}.%(ext)s"
            ydl_optssx = {
                "format": format_id, "outtmpl": fpath, "quiet": True, "no_warnings": True,
                "cookiefile" : cookie_txt_file(), "prefer_ffmpeg": True, "geo_bypass": True, "nocheckcertificate": True,
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])
        # --- End Internal Download Definitions ---

        if songvideo:
            await loop.run_in_executor(None, song_video_dl)
            fpath = f"downloads/{title}.mp4"
            return fpath
        elif songaudio:
            await loop.run_in_executor(None, song_audio_dl)
            fpath = f"downloads/{title}.mp3"
            return fpath
        elif video:
            if await is_on_off(1):
                # Scenario 1: Setting favors download/local file (direct=True means local file path)
                direct = True
                downloaded_file = await loop.run_in_executor(None, video_dl)
            else:
                # Scenario 2: Setting favors streaming (direct=False means stream URL)
                status, stream_url = await self.video(link) # Use the efficient video method
                
                if status == 1:
                    downloaded_file = stream_url
                    direct = False
                else:
                   # Fallback to download if streaming URL fails and size allows
                   file_size = await check_file_size(link)
                   if not file_size:
                     print("None file Size")
                     return
                   total_size_mb = file_size / (1024 * 1024)
                   # 250MB size limit check (as per original code intent)
                   if total_size_mb > 250:
                     print(f"File size {total_size_mb:.2f} MB exceeds the 250MB limit. Cannot download.")
                     return None
                   direct = True
                   downloaded_file = await loop.run_in_executor(None, video_dl)
        else:
            # Default to audio download
            direct = True
            downloaded_file = await loop.run_in_executor(None, audio_dl)
            
        return downloaded_file, direct
