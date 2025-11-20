import os
import re

import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from unidecode import unidecode
from youtubesearchpython.__future__ import VideosSearch

from EsproMusic import app
from config import YOUTUBE_IMG_URL


def changeImageSize(maxWidth, maxHeight, image):
    """Resizes an image while maintaining aspect ratio."""
    widthRatio = maxWidth / image.size[0]
    heightRatio = maxHeight / image.size[1]
    newWidth = int(widthRatio * image.size[0])
    newHeight = int(heightRatio * image.size[1])
    newImage = image.resize((newWidth, newHeight))
    return newImage


def clear(text):
    """Truncates text to fit within approximately 60 characters for display as a title."""
    list = text.split(" ")
    title = ""
    for i in list:
        if len(title) + len(i) < 60:
            title += " " + i
    return title.strip()


async def gen_thumb(videoid):
    """
    Generates a custom thumbnail by fetching YouTube data, processing the image, 
    and drawing custom overlays.
    """
    if os.path.isfile(f"cache/{videoid}.png"):
        return f"cache/{videoid}.png"

    url = f"https://www.youtube.com/watch?v={videoid}"
    
    try:
        results = VideosSearch(url, limit=1)
        video_data = (await results.next())["result"][0]
        
        # Extract and clean data
        try:
            title = video_data["title"]
            title = re.sub("\W+", " ", title)
            title = title.title()
        except:
            title = "Unsupported Title"
        
        duration = video_data.get("duration", "Unknown Mins")
        thumbnail = video_data["thumbnails"][0]["url"].split("?")[0]
        views = video_data.get("viewCount", {}).get("short", "Unknown Views")
        channel = video_data.get("channel", {}).get("name", "Unknown Channel")

        # Download the original thumbnail
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                if resp.status == 200:
                    f = await aiofiles.open(f"cache/thumb{videoid}.png", mode="wb")
                    await f.write(await resp.read())
                    await f.close()

        # Image Processing and Background creation
        youtube = Image.open(f"cache/thumb{videoid}.png")
        image1 = changeImageSize(1280, 720, youtube)
        image2 = image1.convert("RGBA")
        background = image2.filter(filter=ImageFilter.BoxBlur(10)) # Heavy blur
        enhancer = ImageEnhance.Brightness(background)
        background = enhancer.enhance(0.5) # Darkens the background
        
        draw = ImageDraw.Draw(background)
        
        # Load Fonts (Requires font files in assets directory)
        arial = ImageFont.truetype("EsproMusic/assets/font2.ttf", 30)
        font = ImageFont.truetype("EsproMusic/assets/font.ttf", 30)
        
        # Draw Text and Graphics Overlays
        
        # App Name (Top Right)
        draw.text((1110, 8), unidecode(app.name), fill="white", font=arial)
        
        # Channel & Views (Bottom Left)
        draw.text(
            (55, 560),
            f"{channel} | {views[:23]}",
            (255, 255, 255),
            font=arial,
        )
        
        # Title (Top Left)
        draw.text(
            (57, 60),
            clear(title),
            (255, 255, 255),
            font=font,
        )
        
        # Progress Bar Line
        draw.line(
            [(55, 660), (1220, 660)],
            fill="white",
            width=5,
            joint="curve",
        )
        
        # Progress Bar Dot (Fixed position for '00:00' start)
        draw.ellipse(
            [(918, 648), (942, 672)],
            outline="white",
            fill="white",
            width=15,
        )
        
        # Current Time (Fixed to 00:00)
        draw.text(
            (36, 685),
            "00:00",
            (255, 255, 255),
            font=arial,
        )
        
        # Duration (Bottom Right)
        draw.text(
            (1185, 685),
            f"{duration[:23]}",
            (255, 255, 255),
            font=arial,
        )
        
        # Cleanup and Save
        try:
            os.remove(f"cache/thumb{videoid}.png")
        except:
            pass
        
        background.save(f"cache/{videoid}.png")
        return f"cache/{videoid}.png"
        
    except Exception as e:
        print(e)
        # Return fallback image on failure
        return YOUTUBE_IMG_URL
