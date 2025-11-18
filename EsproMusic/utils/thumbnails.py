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
        # Cache
        cache_path = f"cache/{videoid}.png"
        if os.path.isfile(cache_path):
            return cache_path

        url = f"https://www.youtube.com/watch?v={videoid}"
        results = VideosSearch(url, limit=1)
        data = (await results.next())["result"][0]

        # Metadata
        title = re.sub(r"\W+", " ", data.get("title", "No Title")).title()
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

        # Blur background
        bg = base.filter(ImageFilter.GaussianBlur(18))
        bg = ImageEnhance.Brightness(bg).enhance(0.45)

        # === THUMBNAIL FRAME CENTERED ===
        img_w, img_h = 900, 450    # bigger frame
        x_offset = (1280 - img_w) // 2
        y_offset = (720 - img_h) // 2 - 40

        small = youtube.resize((img_w, img_h))
        radius = 35

        mask = Image.new("L", (img_w, img_h), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.rounded_rectangle((0, 0, img_w, img_h), radius=radius, fill=255)
        bg.paste(small, (x_offset, y_offset), mask)

        draw = ImageDraw.Draw(bg)

        # Fonts
        try:
            font_title = ImageFont.truetype("EsproMusic/assets/font.ttf", 46)
            font_meta = ImageFont.truetype("EsproMusic/assets/font2.ttf", 30)
        except:
            font_title = ImageFont.load_default()
            font_meta = ImageFont.load_default()

        # Border outline
        draw.rounded_rectangle(
            (x_offset - 5, y_offset - 5, x_offset + img_w + 5, y_offset + img_h + 5),
            radius=radius + 5,
            outline="white",
            width=6
        )

        # === 3 DOT ICON (TOP RIGHT) ===
        dot_x = x_offset + img_w - 40
        dot_y = y_offset + 25
        for i in range(3):
            draw.ellipse(
                (dot_x, dot_y + (i * 22), dot_x + 14, dot_y + 14),
                fill="white"
            )

        # App Name (top-left)
        draw.text(
            (x_offset + 25, y_offset + 25),
            unidecode(app.name),
            font=font_meta,
            fill="white"
        )

        # SONG TITLE
        draw.text(
            (x_offset, y_offset + img_h + 40),
            clear(title),
            font=font_title,
            fill="white"
        )

        # CHANNEL + VIEWS
        draw.text(
            (x_offset, y_offset + img_h + 95),
            f"{channel} | {views}",
            font=font_meta,
            fill="white"
        )

        # === PROGRESS BAR CENTER ===
        bar_y = 640
        bar_x1 = 180
        bar_x2 = 1100

        draw.line((bar_x1, bar_y, bar_x2, bar_y), fill="white", width=7)

        # Knob centered
        knob_x = (bar_x1 + bar_x2) // 2
        draw.ellipse((knob_x - 16, bar_y - 16, knob_x + 16, bar_y + 16), fill="white")

        # Timecodes
        draw.text((bar_x1 - 60, bar_y + 10), "00:00", font=font_meta, fill="white")
        draw.text((bar_x2 + 20, bar_y + 10), duration, font=font_meta, fill="white")

        # Cleanup
        try:
            os.remove(f"cache/thumb{videoid}.png")
        except:
            pass

        bg.save(cache_path)
        return cache_path

    except Exception as e:
        print("Thumbnail Error:", e)
        return YOUTUBE_IMG_URL
