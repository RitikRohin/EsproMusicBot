import os
import random
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
from youtubesearchpython.__future__ import VideosSearch

from EsproMusic import app
from config import YOUTUBE_IMG_URL


OVERLAYS = [
    "EsproMusic/assets/Espro.png",
    "EsproMusic/assets/Espro1.png",
    "EsproMusic/assets/Espro2.png",
    "EsproMusic/assets/Espro3.png",
    "EsproMusic/assets/Espro4.png",
]


async def gen_thumb(videoid):
    try:
        # Randomizer so every time fresh file generate
        random_key = random.randint(1000, 9999)
        cache_path = f"cache/{videoid}_{random_key}.png"

        # YouTube search info
        results = VideosSearch(videoid, limit=1)
        data = (await results.next())["result"][0]
        thumbnail = data["thumbnails"][-1]["url"].split("?")[0]

        os.makedirs("cache", exist_ok=True)
        headers = {"User-Agent": "Mozilla/5.0"}

        # Download YouTube Thumbnail
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail, headers=headers) as resp:
                if resp.status != 200:
                    return YOUTUBE_IMG_URL

                async with aiofiles.open("cache/raw.png", "wb") as f:
                    await f.write(await resp.read())

        # Base image
        youtube = Image.open("cache/raw.png")
        base = youtube.resize((1280, 720)).convert("RGBA")

        # Background cinematic blur
        bg = base.filter(ImageFilter.GaussianBlur(18))
        bg = ImageEnhance.Brightness(bg).enhance(0.45)

        # Center main clip
        img_w, img_h = 900, 450
        x_offset = (1280 - img_w) // 2
        y_offset = (720 - img_h) // 2
        small = youtube.resize((img_w, img_h))

        # Rounded mask
        mask = Image.new("L", (img_w, img_h), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.rounded_rectangle((0, 0, img_w, img_h), radius=35, fill=255)
        bg.paste(small, (x_offset, y_offset), mask)

        draw = ImageDraw.Draw(bg)

        # White Border around video
        draw.rounded_rectangle(
            (x_offset - 5, y_offset - 5, x_offset + img_w + 5 + 2, y_offset + img_h + 5 + 2),
            radius=41,
            outline="white",
            width=6
        )

        # Progress Bar
        line_y = 700
        draw.line((55, line_y, 1225, line_y), fill="white", width=6)

        # Knob on bar
        knob_x = random.randint(75, 1200)
        knob_r = 13
        draw.ellipse(
            (knob_x - knob_r, line_y - knob_r, knob_x + knob_r, line_y + knob_r),
            fill="white"
        )

        # ---- OVERLAY AS FINAL LAYER ----
        try:
            overlay_path = random.choice(OVERLAYS)
            overlay_img = Image.open(overlay_path).convert("RGBA")
            overlay_img.putalpha(255)  # Full opacity
            overlay_img = overlay_img.resize((1280, 720))
            bg.paste(overlay_img, (0, 0), overlay_img)
            print(f"[Overlay Applied]: {overlay_path}")
        except Exception as e:
            print("Overlay Error:", e)

        # Save final image
        bg.save(cache_path)

        # Clean raw download
        try:
            os.remove("cache/raw.png")
        except:
            pass

        return cache_path

    except Exception as e:
        print("Thumbnail Error:", e)
        return YOUTUBE_IMG_URL
