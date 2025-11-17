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
        # Return cache if exists
        cache_path = f"cache/{videoid}.png"
        if os.path.isfile(cache_path):
            return cache_path

        url = f"https://www.youtube.com/watch?v={videoid}"

        # --- YouTube Metadata ---
        results = VideosSearch(url, limit=1)
        data = (await results.next())["result"][0]

        title = re.sub("\W+", " ", data.get("title", "No Title")).title()
        duration = data.get("duration", "Unknown")
        thumbnail = data["thumbnails"][0]["url"].split("?")[0]
        views = data.get("viewCount", {}).get("short", "0 Views")
        channel = data.get("channel", {}).get("name", "Unknown")

        # --- Download Thumbnail with Headers Fix ---
        os.makedirs("cache", exist_ok=True)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://www.youtube.com/"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail, headers=headers) as resp:
                if resp.status != 200:
                    print(f"Error downloading thumbnail: {resp.status}")
                    return YOUTUBE_IMG_URL

                async with aiofiles.open(f"cache/thumb{videoid}.png", "wb") as f:
                    await f.write(await resp.read())

        # --- Image Work ---
        youtube = Image.open(f"cache/thumb{videoid}.png")
        base = youtube.resize((1280, 720)).convert("RGBA")

        # Blur background
        bg = base.filter(ImageFilter.BoxBlur(12))
        enhancer = ImageEnhance.Brightness(bg)
        bg = enhancer.enhance(0.55)

        # Frame Sizes
        img_w, img_h = 1180, 600
        x_offset = (1280 - img_w) // 2
        y_offset = 30

        # Rounded mask
        small = youtube.resize((img_w, img_h))
        radius = 35

        mask = Image.new("L", (img_w, img_h), 0)
        draw_mask = ImageDraw.Draw(mask)

        draw_mask.rounded_rectangle(
            (0, 0, img_w, img_h),
            radius=radius,
            fill=255
        )

        # Paste main image
        bg.paste(small, (x_offset, y_offset), mask)

        # Draw elements
        draw = ImageDraw.Draw(bg)

        # Fonts
        try:
            font_title = ImageFont.truetype("EsproMusic/assets/font.ttf", 42)
            font_meta = ImageFont.truetype("EsproMusic/assets/font2.ttf", 28)
        except:
            font_title = ImageFont.load_default()
            font_meta = ImageFont.load_default()

        # White border around image
        draw.rounded_rectangle(
            (x_offset - 5, y_offset - 5, x_offset + img_w + 5, y_offset + img_h + 5),
            radius=radius + 6,
            outline="white",
            width=5
        )

        # App Name
        draw.text(
            (x_offset + 10, y_offset + 10),
            unidecode(app.name),
            font=font_meta,
            fill="white"
        )

        # Title
        title_short = clear(title)
        draw.text(
            (x_offset, y_offset + img_h + 15),
            title_short,
            font=font_title,
            fill="white"
        )

        # Channel + Views
        meta_text = f"{channel} | {views}"
        draw.text(
            (x_offset, y_offset + img_h + 60),
            meta_text,
            font=font_meta,
            fill="white"
        )

        # Progress bar
        line_y = 700
        draw.line(
            (55, line_y, 1220, line_y),
            fill="white",
            width=5
        )

        # Progress knob
        draw.ellipse(
            (920, line_y - 12, 940, line_y + 12),
            fill="white"
        )

        # Timecodes
        draw.text((40, line_y + 10), "00:00", font=font_meta, fill="white")
        draw.text((1180, line_y + 10), duration, font=font_meta, fill="white")

        # Cleanup small thumb
        try:
            os.remove(f"cache/thumb{videoid}.png")
        except:
            pass

        # Save final thumbnail
        bg.save(cache_path)
        return cache_path

    except Exception as e:
        print("Thumbnail Error:", e)
        return YOUTUBE_IMG_URL
