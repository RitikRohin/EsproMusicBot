import random
import logging
import os
import re
import aiofiles
import aiohttp
import asyncio
import traceback
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from youtubesearchpython.__future__ import VideosSearch

logging.basicConfig(level=logging.INFO)

def changeImageSize(maxWidth, maxHeight, image):
    """Resizes an image while maintaining its aspect ratio."""
    widthRatio = maxWidth / image.size[0]
    heightRatio = maxHeight / image.size[1]
    newWidth = int(widthRatio * image.size[0])
    newHeight = int(heightRatio * image.size[1])
    newImage = image.resize((newWidth, newHeight))
    return newImage

def truncate(text):
    """Truncates text to a single line for better formatting."""
    if len(text) > 40:
        return text[:40] + "..."
    return text

def random_color():
    """Generates a random RGB color tuple."""
    return (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

def draw_rounded_rectangle(image, xy, radius, fill_color):
    """Draws a rounded rectangle using a mask."""
    x1, y1, x2, y2 = xy
    mask = Image.new('L', image.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=255)
    
    fill_layer = Image.new('RGBA', image.size, fill_color)
    image.paste(fill_layer, (0,0), mask)

def draw_text_with_shadow(background, draw, position, text, font, fill, shadow_offset=(3, 3), shadow_blur=5):
    """Draws text with a shadow for better visibility."""
    shadow = Image.new('RGBA', background.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.text(position, text, font=font, fill="black")
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=shadow_blur))
    background.paste(shadow, shadow_offset, shadow)
    draw.text(position, text, font=font, fill=fill)

async def gen_thumb(videoid: str):
    """Generates a unique thumbnail for a given YouTube video ID."""
    try:
        # Check for cached thumbnail
        if os.path.isfile(f"cache/{videoid}_v5.png"):
            logging.info(f"Using cached thumbnail for {videoid}")
            return f"cache/{videoid}_v5.png"

        url = f"https://www.youtube.com/watch?v={videoid}"
        results = VideosSearch(url, limit=1)
        video_info = (await results.next())["result"][0]
        
        title = truncate(re.sub("\W+", " ", video_info.get("title", "Unsupported Title")).title())
        duration = video_info.get("duration", "Live")
        thumbnail_url = video_info.get("thumbnails", [{}])[0].get("url", "").split("?")[0]
        views = video_info.get("viewCount", {}).get("short", "Unknown Views")
        channel = video_info.get("channel", {}).get("name", "Unknown Channel")

        # Download thumbnail
        if not thumbnail_url:
            logging.error("Thumbnail URL not found.")
            return None

        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail_url) as resp:
                content = await resp.read()
                if resp.status != 200:
                    logging.error(f"Failed to download thumbnail: {resp.status}")
                    return None
                
                download_path = f"cache/thumb_{videoid}.png"
                async with aiofiles.open(download_path, mode="wb") as f:
                    await f.write(content)
                    
        # Image Processing
        original_thumb = Image.open(download_path)
        original_thumb = changeImageSize(1280, 720, original_thumb)
        
        background = original_thumb.convert("RGBA").filter(filter=ImageFilter.BoxBlur(20))
        enhancer = ImageEnhance.Brightness(background)
        background = enhancer.enhance(0.6)

        draw = ImageDraw.Draw(background)
        arial = ImageFont.truetype("EsproMusic/assets/font2.ttf", 30)
        title_font = ImageFont.truetype("EsproMusic/assets/font3.ttf", 35)

        # Draw the main rounded-rectangle thumbnail
        thumb_width, thumb_height = 800, 450
        thumb_x, thumb_y = (1280 - thumb_width) // 2, 60
        main_thumb_resized = original_thumb.resize((thumb_width, thumb_height))

        mask = Image.new('L', main_thumb_resized.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([(0,0), (thumb_width, thumb_height)], radius=25, fill=255)
        
        background.paste(main_thumb_resized, (thumb_x, thumb_y), mask)

        # Draw text and info below the thumbnail
        text_y_position = thumb_y + thumb_height + 40
        draw_text_with_shadow(background, draw, (300, text_y_position), title, title_font, (255, 255, 255))
        
        text_y_position += 50
        info_text = f"{channel} | {views}"
        draw_text_with_shadow(background, draw, (300, text_y_position), info_text, arial, (200, 200, 200))

        # Gradient Progress Bar
        bar_y_position = text_y_position + 60
        bar_x_position = (1280 - 1000) // 2
        bar_length = 1000
        
        draw.line([bar_x_position, bar_y_position, bar_x_position + bar_length, bar_y_position], fill=(200, 200, 200), width=8)

        progress_percentage = random.uniform(0.1, 0.9)
        progress_length = int(bar_length * progress_percentage)
        
        progress_end_color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        
        progress_layer = Image.new('RGB', (progress_length, 8))
        progress_draw = ImageDraw.Draw(progress_layer)
        for i in range(progress_length):
            r = int(progress_end_color[0] * (i/progress_length))
            g = int(progress_end_color[1] * (i/progress_length))
            b = int(progress_end_color[2] * (i/progress_length))
            progress_draw.line((i, 0, i, 8), fill=(r,g,b))
            
        background.paste(progress_layer, (bar_x_position, bar_y_position - 4))
        
        circle_radius = 15
        circle_x_position = bar_x_position + progress_length
        draw.ellipse([circle_x_position - circle_radius, bar_y_position - circle_radius,
                      circle_x_position + circle_radius, bar_y_position + circle_radius], fill=(255, 0, 255))
        
        # Draw time stamps and play icons
        draw_text_with_shadow(background, draw, (bar_x_position, bar_y_position + 15), "00:00", arial, (255, 255, 255))
        draw_text_with_shadow(background, draw, (bar_x_position + bar_length - 70, bar_y_position + 15), duration, arial, (255, 255, 255))

        play_icons = Image.open("EsproMusic/assets/play_icons.png")
        play_icons = play_icons.resize((500, 50))
        icon_y_position = bar_y_position + 70
        icon_x_position = (1280 - 500) // 2
        background.paste(play_icons, (icon_x_position, icon_y_position), play_icons)
        
        os.remove(download_path)
        background_path = f"cache/{videoid}_v5.png"
        background.save(background_path)
        
        return background_path

    except Exception as e:
        logging.error(f"Error generating new thumbnail for video {videoid}: {e}")
        traceback.print_exc()
        return None

if __name__ == "__main__":
    VIDEO_ID = "3Z_x7vBqr6E" 
    
    if not os.path.exists("cache"):
        os.makedirs("cache")
    if not os.path.exists("EsproMusic/assets"):
        os.makedirs("EsproMusic/assets")
        print("Please place your font files and 'play_icons.png' in the EsproMusic/assets/ folder.")
    
    async def main():
        thumbnail_path = await gen_thumb(VIDEO_ID)
        if thumbnail_path:
            print(f"Thumbnail created successfully at: {thumbnail_path}")
    
    asyncio.run(main())
