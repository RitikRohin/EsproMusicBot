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
        cache_path = f"cache/{videoid}.png"

        # Force refresh for new overlay every time
        if os.path.isfile(cache_path):
            os.remove(cache_path)

        # Search YouTube properly
        results = VideosSearch(videoid, limit=1)
        data = (await results.next())["result"][0]
        thumbnail = data["thumbnails"][-1]["url"].split("?")[0]

        os.makedirs("cache", exist_ok=True)
        headers = {"User-Agent": "Mozilla/5.0"}

        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail, headers=headers) as resp:
                if resp.status != 200:
                    return YOUTUBE_IMG_URL

                async with aiofiles.open(f"cache/thumb{videoid}.png", "wb") as f:
                    await f.write(await resp.read())

        # Load base image
        youtube = Image.open(f"cache/thumb{videoid}.png")
        base = youtube.resize((1280, 720)).convert("RGBA")

        # Blurred BG Layer
        bg = base.filter(ImageFilter.GaussianBlur(18))
        bg = ImageEnhance.Brightness(bg).enhance(0.45)

        # Main thumbnail area
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

        # Border
        draw.rounded_rectangle(
            (x_offset - 5, y_offset - 5, x_offset + img_w + 5, y_offset + img_h + 5),
            radius=41,
            outline="white",
            width=5
        )

        # Progress Bar
        line_y = 700
        draw.line((55, line_y, 1225, line_y), fill="white", width=6)

        # Random Knob position
        knob_x = random.randint(75, 1200)
        knob_r = 13
        draw.ellipse(
            (knob_x - knob_r, line_y - knob_r, knob_x + knob_r, line_y + knob_r),
            fill="white"
        )

        # ---- OVERLAY ON TOP ----
        try:
            overlay_path = random.choice(OVERLAYS)
            overlay_img = Image.open(overlay_path).convert("RGBA")
            overlay_img = overlay_img.resize((1280, 720))
            bg.paste(overlay_img, (0, 0), overlay_img)
            print(f"Overlay Applied (TOP): {overlay_path}")
        except Exception as e:
            print("Overlay Error:", e)

        # Cleanup
        try:
            os.remove(f"cache/thumb{videoid}.png")
        except:
            pass

        # Final Save
        bg.save(cache_path)
        return cache_path

    except Exception as e:
        print("Thumbnail Error:", e)
        return YOUTUBE_IMG_URL
