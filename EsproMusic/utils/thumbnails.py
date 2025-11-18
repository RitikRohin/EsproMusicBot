import os
import re
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from unidecode import unidecode
from youtubesearchpython.__future__ import VideosSearch

from EsproMusic import app
from config import YOUTUBE_IMG_URL


def clear(text):
    words = text.split(" ")
    title = ""
    for w in words:
        if len(title) + len(w) < 40:
            title += " " + w
    return title.strip()


async def gen_thumb(videoid):
    try:
        # Cache check
        cache_path = f"cache/{videoid}.png"
        if os.path.isfile(cache_path):
            return cache_path

        url = f"https://www.youtube.com/watch?v={videoid}"
        results = VideosSearch(url, limit=1)
        data = (await results.next())["result"][0]

        # Metadata
        title = re.sub("\W+", " ", data.get("title", "No Title")).title()
        duration = data.get("duration", "Unknown")
        thumbnail = data["thumbnails"][0]["url"].split("?")[0]
        views = data.get("viewCount", {}).get("short", "0 Views")
        channel = data.get("channel", {}).get("name", "Unknown")

        os.makedirs("cache", exist_ok=True)

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.youtube.com/"
        }

        # Download thumbnail
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail, headers=headers) as resp:
                if resp.status != 200:
                    return YOUTUBE_IMG_URL

                async with aiofiles.open(f"cache/thumb{videoid}.png", "wb") as f:
                    await f.write(await resp.read())

        youtube = Image.open(f"cache/thumb{videoid}.png")
        base = youtube.resize((1280, 720)).convert("RGBA")

        # Background blur
        bg = base.filter(ImageFilter.GaussianBlur(18))
        bg = ImageEnhance.Brightness(bg).enhance(0.45)

        # --- FINAL FRAME SIZE ---
        img_w, img_h = 750, 380
        x_offset = (1280 - img_w) // 2
        y_offset = 35

        small = youtube.resize((img_w, img_h))
        radius = 30

        # Rounded rectangle mask
        mask = Image.new("L", (img_w, img_h), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.rounded_rectangle((0, 0, img_w, img_h), radius=radius, fill=255)

        bg.paste(small, (x_offset, y_offset), mask)

        draw = ImageDraw.Draw(bg)

        # Fonts
        try:
            font_title = ImageFont.truetype("EsproMusic/assets/font.ttf", 42)
            font_meta = ImageFont.truetype("EsproMusic/assets/font2.ttf", 28)
        except:
            font_title = ImageFont.load_default()
            font_meta = ImageFont.load_default()

        # Border around thumbnail
        draw.rounded_rectangle(
            (x_offset - 5, y_offset - 5, x_offset + img_w + 5, y_offset + img_h + 5),
            radius=radius + 5,
            outline="white",
            width=5
        )

        # App name
        draw.text(
            (x_offset + 18, y_offset + 18),
            unidecode(app.name),
            font=font_meta,
            fill="white"
        )

        # Title
        draw.text(
            (x_offset, y_offset + img_h + 30),
            clear(title),
            font=font_title,
            fill="white"
        )

        # Channel + Views
        meta_text = f"{channel} | {views}"
        draw.text(
            (x_offset, y_offset + img_h + 80),
            meta_text,
            font=font_meta,
            fill="white"
        )

        # Progress bar
        line_y = 700
        draw.line((55, line_y, 1225, line_y), fill="white", width=6)

        # Knob
        draw.ellipse((930, line_y - 13, 960, line_y + 13), fill="white")

        # Timecodes
        draw.text((40, line_y + 10), "00:00", font=font_meta, fill="white")
        draw.text((1170, line_y + 10), duration, font=font_meta, fill="white")

        # Cleanup temp file
        try:
            os.remove(f"cache/thumb{videoid}.png")
        except:
            pass

        bg.save(cache_path)
        return cache_path

    except Exception as e:
        print("Thumbnail Error:", e)
        return YOUTUBE_IMG_URL
