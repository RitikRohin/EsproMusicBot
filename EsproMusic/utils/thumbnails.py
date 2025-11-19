import os
import re
import os
import re
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from unidecode import unidecode
from youtubesearchpython.__future__ import VideosSearch

from EsproMusic import app
from config import YOUTUBE_IMG_URL

OVERLAY_IMAGE_PATH = "EsproMusic/assets/Espro.png"


async def download_image(url, filename):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.youtube.com/"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return False

                async with aiofiles.open(filename, "wb") as f:
                    await f.write(await resp.read())
        return True
    except:
        return False


async def gen_thumb(videoid):
    try:
        cache_path = f"cache/{videoid}.png"
        if os.path.isfile(cache_path):
            return cache_path

        os.makedirs("cache", exist_ok=True)

        # --- Get YouTube thumbnail data ---
        url = f"https://www.youtube.com/watch?v={videoid}"
        results = VideosSearch(url, limit=1)
        data = (await results.next())["result"][0]

        thumbnail = data["thumbnails"][-1]["url"]   # highest size thumbnail

        # --- Download main thumbnail ---
        main_thumb = f"cache/{videoid}_main"
        if not await download_image(thumbnail, main_thumb):
            # Fallback #1: High quality direct URL
            fallback_url = f"https://img.youtube.com/vi/{videoid}/maxresdefault.jpg"
            if not await download_image(fallback_url, main_thumb):
                return YOUTUBE_IMG_URL

        # --- Pillow load fix for WEBP / JPG / PNG ---
        try:
            youtube = Image.open(main_thumb).convert("RGBA")
        except:
            youtube = Image.open(main_thumb).convert("RGB").convert("RGBA")

        # --- Resize to full resolution ---
        base = youtube.resize((1280, 720)).convert("RGBA")

        # --- Background blur ---
        bg = base.filter(ImageFilter.GaussianBlur(18))
        bg = ImageEnhance.Brightness(bg).enhance(0.45)

        # --- Overlay image on top (must be first layer) ---
        try:
            overlay_img = Image.open(OVERLAY_IMAGE_PATH).convert("RGBA")
            overlay_img = overlay_img.resize((1280, 720))
            bg.paste(overlay_img, (0, 0), overlay_img)
        except:
            pass

        # --- Main centered thumbnail ---
        img_w, img_h = 900, 450
        x_offset = (1280 - img_w) // 2
        y_offset = (720 - img_h) // 2

        small = youtube.resize((img_w, img_h))

        # Rounded corners
        mask = Image.new("L", (img_w, img_h), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.rounded_rectangle((0, 0, img_w, img_h), radius=35, fill=255)

        bg.paste(small, (x_offset, y_offset), mask)

        draw = ImageDraw.Draw(bg)

        # Thumbnail border
        draw.rounded_rectangle(
            (x_offset - 5, y_offset - 5, x_offset + img_w + 5, y_offset + img_h + 5),
            radius=41, outline="white", width=5
        )

        # Progress bar
        line_y = 700
        draw.line((55, line_y, 1225, line_y), fill="white", width=6)

        # Knob
        knob_x = 930
        knob_r = 13
        draw.ellipse(
            (knob_x - knob_r, line_y - knob_r, knob_x + knob_r, line_y + knob_r),
            fill="white"
        )

        bg.save(cache_path)

        return cache_path

    except Exception as e:
        print("Thumbnail Error:", e)
        return YOUTUBE_IMG_URL
