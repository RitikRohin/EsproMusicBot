import os
import re
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from unidecode import unidecode
from youtubesearchpython.__future__ import VideosSearch

from EsproMusic import app
# Make sure to replace 'config' import if not using it
from config import YOUTUBE_IMG_URL 

# Define the path to the image you want to overlay
# UPDATED PATH based on your request:
OVERLAY_IMAGE_PATH = "EsproMusic/assets/Espro.png" 


async def gen_thumb(videoid):
    try:
        cache_path = f"cache/{videoid}.png"
        if os.path.isfile(cache_path):
            return cache_path

        url = f"https://www.youtube.com/watch?q={videoid}"
        results = VideosSearch(url, limit=1)
        data = (await results.next())["result"][0]

        thumbnail = data["thumbnails"][0]["url"].split("?")[0]

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

        # Center thumbnail (900×450)
        img_w, img_h = 900, 450
        x_offset = (1280 - img_w) // 2
        y_offset = (720 - img_h) // 2

        small = youtube.resize((img_w, img_h))
        radius = 35

        # Rounded mask
        mask = Image.new("L", (img_w, img_h), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.rounded_rectangle((0, 0, img_w, img_h), radius=radius, fill=255)

        # Paste thumbnail
        bg.paste(small, (x_offset, y_offset), mask)

        draw = ImageDraw.Draw(bg)

        # Border around thumbnail
        draw.rounded_rectangle(
            (x_offset - 5, y_offset - 5, x_offset + img_w + 5, y_offset + img_h + 5),
            radius=radius + 6,
            outline="white",
            width=5
        )

        # --- PROGRESS BAR ---
        line_y = 700
        draw.line((55, line_y, 1225, line_y), fill="white", width=6)

        # --- KNOB (circle) ---
        # Center knob on bar → x = 930 (editable), y = line_y
        knob_x = 930
        knob_r = 13
        draw.ellipse(
            (knob_x - knob_r, line_y - knob_r, knob_x + knob_r, line_y + knob_r),
            fill="white"
        )
        
        # ----------------------------------------
        # --- NEW CODE: PASTE THE OVERLAY IMAGE ---
        # ----------------------------------------
        try:
            overlay_img = Image.open(OVERLAY_IMAGE_PATH).convert("RGBA")
            
            # Since the image you provided covers the full 1280x720 area of your thumbnail
            # based on its appearance, we'll resize it to fit the whole background (bg).
            overlay_img = overlay_img.resize((1280, 720))

            # Coordinates to paste the top-left corner of the overlay (0, 0 for full coverage)
            x_overlay = 0
            y_overlay = 0 

            # Paste the overlay onto the background using its alpha channel as a mask
            bg.paste(overlay_img, (x_overlay, y_overlay), overlay_img)

        except FileNotFoundError:
            print(f"Overlay image not found at: {OVERLAY_IMAGE_PATH}. Please check the path and file name. Skipping overlay.")
        except Exception as e:
            print(f"Error applying overlay image: {e}")
        # ----------------------------------------
        # --- END NEW CODE ---
        # ----------------------------------------

        # Clean temp file
        try:
            os.remove(f"cache/thumb{videoid}.png")
        except:
            pass

        bg.save(cache_path)
        return cache_path

    except Exception as e:
        print("Thumbnail Error:", e)
        return YOUTUBE_IMG_URL
