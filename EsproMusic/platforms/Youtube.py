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
from pyrogram import Client
from EsproMusic import app

# --- यहाँ अपनी जानकारी डालें ---

# Pyrogram API ID और API HASH
API_ID = 12380656
API_HASH = "d927c13beaaf5110f25c505b7c071273"

# Telegram चैनल की ID
TELEGRAM_CHANNEL_ID = -1002945056537

# --- Cache JSON File ---
CACHE_FILE = "cache_data.json"

def get_cache_data():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_cache_data(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f, indent=4)

# --- Helpers ---
def cookie_txt_file():
    folder_path = f"{os.getcwd()}/cookies"
    txt_files = glob.glob(os.path.join(folder_path, '*.txt'))
    if not txt_files:
        raise FileNotFoundError("No .txt files found in the specified folder.")
    cookie_txt_file = random.choice(txt_files)
    filename = f"{os.getcwd()}/cookies/logs.csv"
    with open(filename, 'a') as file:
        file.write(f'Choosen File : {cookie_txt_file}\n')
    return f"""cookies/{str(cookie_txt_file).split("/")[-1]}"""

async def check_file_size(link):
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
            if 'filesize' in format:
                total_size += format['filesize']
        return total_size

    info = await get_format_info(link)
    if info is None:
        return None
    formats = info.get('formats', [])
    if not formats:
        print("No formats found.")
        return None
    return parse_size(formats)

async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")

# --- Missing Functions Fix ---
def time_to_seconds(time_str: str) -> int:
    if not time_str:
        return 0
    parts = list(map(int, time_str.split(":")))
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    elif len(parts) == 2:
        return parts[0] * 60 + parts[1]
    else:
        return parts[0]

async def is_on_off(val: int) -> bool:
    # फिलहाल हर बार True return करेगा
    return True

# --- YouTube API Class ---
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
        return bool(re.search(self.regex, link))

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
        return text[offset: offset + length]

    async def search(self, query: str, limit: int = 10) -> list:
        results = VideosSearch(query, limit=limit)
        search_results = []
        for result in (await results.next())["result"]:
            search_results.append({
                "title": result["title"],
                "duration_min": result["duration"],
                "thumbnail": result["thumbnails"][0]["url"].split("?")[0],
                "vidid": result["id"],
                "link": result["link"]
            })
        return search_results

    async def upload_to_channel(self, client, chat_id, file_path, yt_id, title):
        try:
            if file_path.endswith((".mp3", ".ogg")):
                msg = await client.send_audio(chat_id, file_path,
                                              caption=f"**{title}**\n\n**YouTube ID:** `{yt_id}`")
            elif file_path.endswith((".mp4", ".mkv")):
                msg = await client.send_video(chat_id, file_path,
                                              caption=f"**{title}**\n\n**YouTube ID:** `{yt_id}`")
            cache_data = get_cache_data()
            cache_data[yt_id] = msg.id
            save_cache_data(cache_data)
            print(f"File uploaded to channel and cached: {yt_id}")
            return True
        except Exception as e:
            print(f"Error uploading to channel: {e}")
            return False

    async def find_and_download_from_channel(self, client, chat_id, yt_id, title):
        cache_data = get_cache_data()
        if yt_id in cache_data:
            tg_msg_id = cache_data[yt_id]
            try:
                msg = await client.get_messages(chat_id, tg_msg_id)
                if msg:
                    file_path = await client.download_media(msg, file_name=f"downloads/{title}")
                    print(f"File found in channel and downloaded: {file_path}")
                    return file_path
            except Exception as e:
                print(f"Error fetching file from channel: {e}")
                del cache_data[yt_id]
                save_cache_data(cache_data)
                return None
        return None

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
            if str(duration_min) == "None":
                duration_sec = 0
            else:
                duration_sec = int(time_to_seconds(duration_min))
        return title, duration_min, duration_sec, thumbnail, vidid

    # बाकी methods unchanged (title, duration, thumbnail, video, playlist, track, formats, slider, download)
    # [आपके original code जैसे ही रहेंगे, क्योंकि वो सही थे]
    # --- For brevity मैंने यहाँ वही रखा जो fix जरूरी था ---

    # Full download function आपके original जैसा ही रहेगा

# --- Main Test ---
async def main():
    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    client = app
    print(f"Client object is valid: {client is not None}")

    yt_api = YouTubeAPI()
    link_to_download = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    title_of_song = "Never Gonna Give You Up"

    async with client:
        print("पहली बार डाउनलोड कर रहा हूँ...")
        file_path, is_direct = await yt_api.download(
            link=link_to_download,
            mystic=None,
            songaudio=True,
            title=title_of_song,
            client=client,
            channel_id=TELEGRAM_CHANNEL_ID
        )
        print(f"डाउनलोड किया गया: {file_path}")

        print("\nदूसरी बार डाउनलोड कर रहा हूँ...")
        file_path_2, is_direct_2 = await yt_api.download(
            link=link_to_download,
            mystic=None,
            songaudio=True,
            title=title_of_song,
            client=client,
            channel_id=TELEGRAM_CHANNEL_ID
        )
        print(f"डाउनलोड किया गया: {file_path_2}")

if __name__ == "__main__":
    asyncio.run(main())
