import asyncio
import os
import re
import json
from typing import Union
import logging # Added logging import for better practice

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

# Assuming these imports exist in your project structure
from EsproMusic.utils.database import is_on_off
from EsproMusic.utils.formatters import time_to_seconds

import glob
import random

# Setup logging (optional, but good practice)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def cookie_txt_file():
    folder_path = f"{os.getcwd()}/cookies"
    filename = f"{os.getcwd()}/cookies/logs.csv"
    txt_files = glob.glob(os.path.join(folder_path, '*.txt'))
    if not txt_files:
        # Changed to logging.error and raised a more specific exception
        logging.error("No .txt files found in the specified folder: %s", folder_path)
        raise FileNotFoundError("No .txt files found in the specified folder.")
        
    cookie_txt_file = random.choice(txt_files)
    
    # Ensure the cookies directory exists before writing the log file
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    try:
        with open(filename, 'a') as file:
            file.write(f'Choosen File : {cookie_txt_file}\n')
    except IOError as e:
        logging.warning(f"Could not write to log file {filename}: {e}")

    # Return the path relative to the working directory, stripped of the full path
    return f"""cookies/{os.path.basename(cookie_txt_file)}"""


async def check_file_size(link):
    async def get_format_info(link):
        try:
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
                logging.error(f'YTDL Error for size check:\n{stderr.decode()}')
                return None
            return json.loads(stdout.decode())
        except FileNotFoundError:
            logging.error("yt-dlp command not found. Ensure it is installed and in your PATH.")
            return None
        except Exception as e:
            logging.error(f"An unexpected error occurred during size check: {e}")
            return None

    def parse_size(formats):
        total_size = 0
        for format in formats:
            # Use 'filesize_approx' if 'filesize' is not available for better estimation
            size = format.get('filesize') or format.get('filesize_approx')
            if size:
                total_size += size
        return total_size

    info = await get_format_info(link)
    if info is None:
        return None
    
    formats = info.get('formats', [])
    # If formats are not found, check top-level keys like 'filesize' or 'filesize_approx'
    if not formats:
        total_size = info.get('filesize') or info.get('filesize_approx')
        if total_size:
            return total_size
        logging.warning("No formats found and no top-level filesize info.")
        return None
    
    total_size = parse_size(formats)
    return total_size

async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    
    out_decoded = out.decode("utf-8", errors='ignore')
    errorz_decoded = errorz.decode("utf-8", errors='ignore')
    
    if errorz_decoded:
        if "unavailable videos are hidden" in errorz_decoded.lower():
            return out_decoded
        else:
            return errorz_decoded
    return out_decoded


class YouTubeAPI:
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
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
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
        # Handle async next() result more robustly
        search_result = (await results.next())["result"]
        if not search_result:
             raise ValueError("No results found for the given link.")

        result = search_result[0]
        title = result["title"]
        duration_min = result["duration"]
        thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        vidid = result["id"]
        if str(duration_min) == "None":
            duration_sec = 0
        else:
            duration_sec = int(time_to_seconds(duration_min))
        return title, duration_min, duration_sec, thumbnail, vidid

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
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        try:
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
                return 1, stdout.decode().split("\n")[0].strip()
            else:
                return 0, stderr.decode().strip()
        except FileNotFoundError:
            return 0, "yt-dlp command not found."
        except Exception as e:
            return 0, str(e)


    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        # user_id is unused here, removed from f-string for cleanliness
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_txt_file()} --playlist-end {limit} --skip-download {link}"
        )
        try:
            result = [key for key in playlist.split("\n") if key.strip()]
        except:
            result = []
        return result

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        search_result = (await results.next())["result"]
        if not search_result:
             raise ValueError("No results found for the given link.")

        result = search_result[0]
        title = result["title"]
        duration_min = result["duration"]
        vidid = result["id"]
        yturl = result["link"]
        thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ytdl_opts = {"quiet": True, "cookiefile" : cookie_txt_file()}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            try:
                r = ydl.extract_info(link, download=False)
            except yt_dlp.utils.DownloadError as e:
                 logging.error(f"YTDL DownloadError during format extraction: {e}")
                 return [], link
            
            for format in r.get("formats", []):
                try:
                    # Check for mandatory keys
                    if all(key in format for key in ["format_id", "ext"]):
                         formats_available.append(
                            {
                                "format": format.get("format"),
                                "filesize": format.get("filesize") or format.get("filesize_approx"),
                                "format_id": format["format_id"],
                                "ext": format["ext"],
                                "format_note": format.get("format_note"),
                                "yturl": link,
                            }
                        )
                except Exception:
                    continue # Skip invalid format entry
        return formats_available, link

    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: Union[bool, str] = None,
    ):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        if not result or query_type >= len(result):
             raise IndexError(f"Index {query_type} out of bounds for search results.")
             
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic, # Unused parameter, kept for signature consistency
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> Union[tuple[str, bool], str, None]:
        
        if videoid:
            link = self.base + link
            
        loop = asyncio.get_running_loop()

        def audio_dl():
            """Downloads the best available audio (typically m4a/opus) for quick access."""
            ydl_optssx = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile" : cookie_txt_file(),
                "no_warnings": True,
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, False)
            
            # Use info to determine the correct downloaded file path
            ext = info.get('ext', 'mp3') # Default to mp3 if ext not found
            xyz = os.path.join("downloads", f"{info['id']}.{ext}")
            
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            
            # Recheck path after download as it might change depending on yt-dlp's internal logic
            # This is a common pattern for reliable path return
            info = x.extract_info(link, False)
            ext = info.get('ext', 'mp3') 
            return os.path.join("downloads", f"{info['id']}.{ext}")


        def video_dl():
            """Downloads best 720p mp4 video with m4a audio."""
            ydl_optssx = {
                # Force best video (720p) + best audio (m4a) and merge into mp4
                "format": "bestvideo[height<=?720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile" : cookie_txt_file(),
                "no_warnings": True,
                "merge_output_format": "mp4", # Ensure the output is mp4
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, False)
            
            # The output filename will be ID.mp4 because of merge_output_format
            xyz = os.path.join("downloads", f"{info['id']}.mp4") 
            
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            
            # Re-check path
            return os.path.join("downloads", f"{info['id']}.mp4")


        def song_video_dl():
            """Downloads video by specific format_id and merges with audio (fast if format_id is high quality)."""
            # Use format_id for video and 140 (best m4a) for audio
            formats = f"{format_id}+140"
            fpath = f"downloads/{title}.%(ext)s"
            ydl_optssx = {
                "format": formats,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile" : cookie_txt_file(),
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])
            # The merged output will be .mp4
            return f"downloads/{title}.mp4"


        def song_audio_dl():
            """
            *** FAST FIX APPLIED HERE: Removed slow MP3 conversion. ***
            Downloads audio by specific format_id. Returns in original format (e.g., m4a).
            """
            # Use %(ext)s to let yt-dlp determine the file extension based on the format_id
            fpath = f"downloads/{title}.%(ext)s"
            ydl_optssx = {
                "format": format_id,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile" : cookie_txt_file(),
                "prefer_ffmpeg": True,
                # *** REMOVED FFmpeg post-processors for MP3 conversion to speed up download ***
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, False)
            x.download([link])
            
            # Use info to determine the final path
            ext = info.get('ext', 'm4a')
            return f"downloads/{title}.{ext}"


        if songvideo:
            # We assume song_video_dl returns the final path
            fpath = await loop.run_in_executor(None, song_video_dl)
            return fpath
            
        elif songaudio:
            # We assume song_audio_dl returns the final path (e.g., .m4a)
            fpath = await loop.run_in_executor(None, song_audio_dl)
            return fpath
            
        elif video:
            direct = True # Assume direct download first (blocking yt-dlp call)
            downloaded_file = None
            
            # Check for direct URL preference
            if await is_on_off(1):
                # Scenario 1: Blocking Download (direct=True)
                downloaded_file = await loop.run_in_executor(None, video_dl)
            else:
                # Scenario 2: Try to get Direct URL first
                status, stream_url = await self.video(link)
                if status == 1:
                    downloaded_file = stream_url
                    direct = False # It's a direct stream URL, not a downloaded file
                else:
                   # Fallback to Blocking Download if direct URL fails or size is too big
                   logging.warning(f"Failed to get direct stream URL, checking file size: {stream_url}")
                   
                   file_size = await check_file_size(link)
                   
                   # Your original code had a 100MB limit check (comment says 100MB, code uses 250MB)
                   # Keeping the 250MB logic here for consistency
                   if not file_size:
                     logging.warning("Cannot determine file size.")
                     # Fallback to download even if size is unknown
                     downloaded_file = await loop.run_in_executor(None, video_dl)
                   else:
                     total_size_mb = file_size / (1024 * 1024)
                     if total_size_mb > 250:
                         logging.info(f"File size {total_size_mb:.2f} MB exceeds the 250MB limit.")
                         return None
                     
                     # Download if size is acceptable or unknown
                     downloaded_file = await loop.run_in_executor(None, video_dl)
                     direct = True
                     
            if not downloaded_file:
                 return None
                 
            return downloaded_file, direct
            
        else: # Default: Audio download
            direct = True
            downloaded_file = await loop.run_in_executor(None, audio_dl)
            return downloaded_file, direct
