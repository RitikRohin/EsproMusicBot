import os
import re
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from unidecode import unidecode
from youtubesearchpython.__future__ import VideosSearch

# Ensure these imports work in your environment
from EsproMusic import app 
from config import YOUTUBE_IMG_URL 


# Function to resize the image while maintaining aspect ratio
def changeImageSize(maxWidth, maxHeight, image):
    widthRatio = maxWidth / image.size[0]
    heightRatio = maxHeight / image.size[1]
    
    # Calculate new size based on the smaller ratio to ensure fit
    if widthRatio < heightRatio:
        newWidth = maxWidth
        newHeight = int(newWidth / image.size[0] * image.size[1])
    else:
        newHeight = maxHeight
        newWidth = int(newHeight / image.size[1] * image.size[0])
        
    newImage = image.resize((newWidth, newHeight))
    return newImage


# Function to truncate the title to approximately 40 characters
def clear(text):
    list = text.split(" ")
    title = ""
    for i in list:
        # Keep title length manageable for the overlay area
        if len(title) + len(i) < 40: 
            title += " " + i
    return title.strip()


# Main asynchronous function to generate the thumbnail
async def gen_thumb(videoid):
    # Return file from cache if it exists
    if os.path.isfile(f"cache/{videoid}.png"):
        return f"cache/{videoid}.png"

    url = f"https://www.youtube.com/watch?v={videoid}"
    
    try:
        # 1. Fetch metadata from YouTube
        results = VideosSearch(url, limit=1)
        video_data = (await results.next())["result"][0]
        
        # Safely extract and format metadata
        title = video_data.get("title", "Unsupported Title")
        title = re.sub("\W+", " ", title).title()
        duration = video_data.get("duration", "Unknown Mins")
        thumbnail = video_data["thumbnails"][0]["url"].split("?")[0]
        views = video_data.get("viewCount", {}).get("short", "Unknown Views")
        channel = video_data.get("channel", {}).get("name", "Unknown Channel")

        # 2. Download the thumbnail image
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                if resp.status == 200:
                    os.makedirs("cache", exist_ok=True) 
                    f = await aiofiles.open(f"cache/thumb{videoid}.png", mode="wb")
                    await f.write(await resp.read())
                    await f.close()

        # 3. Image Processing (Pillow)
        youtube = Image.open(f"cache/thumb{videoid}.png")
        image1 = changeImageSize(1280, 720, youtube)
        image2 = image1.convert("RGBA")
        
        # 3a. Create blurred and darkened background
        background = image2.filter(filter=ImageFilter.BoxBlur(10))
        enhancer = ImageEnhance.Brightness(background)
        background = enhancer.enhance(0.5)
        
        # --- Rounded Rectangular Frame Logic ---
        
        # Inner image size (centered on 1280x720 canvas)
        img_w, img_h = 1180, 600 
        x_offset = (1280 - img_w) // 2  # 50px
        y_offset = 30 # Top margin for centering the frame

        # 3b. Prepare the inner image and resize
        framed_image = youtube.resize((img_w, img_h)) 
        
        # 3c. Create Rounded Rectangle Mask
        radius = 30 
        img_mask = Image.new('L', (img_w, img_h), 0)
        img_draw_mask = ImageDraw.Draw(img_mask)
        
        # Draw the rounded shape on the mask
        img_draw_mask.rectangle([(0, radius), (img_w, img_h - radius)], fill=255)
        img_draw_mask.rectangle([(radius, 0), (img_w - radius, img_h)], fill=255)
        img_draw_mask.ellipse((0, 0, radius * 2, radius * 2), fill=255) # Top-left
        img_draw_mask.ellipse((img_w - radius * 2, 0, img_w, radius * 2), fill=255) # Top-right
        img_draw_mask.ellipse((0, img_h - radius * 2, radius * 2, img_h), fill=255) # Bottom-left
        img_draw_mask.ellipse((img_w - radius * 2, img_h - radius * 2, img_w, img_h), fill=255) # Bottom-right
        
        # 3d. Paste the framed image onto the background using the mask
        background.paste(framed_image, (x_offset, y_offset), img_mask)
        
        # 3e. Draw White Border
        draw = ImageDraw.Draw(background)
        border_radius = radius + 3 
        # Coordinates for the border (5px padding around the inner image)
        draw.rounded_rectangle((x_offset - 5, y_offset - 5, x_offset + img_w + 5, y_offset + img_h + 5), radius=border_radius, outline="white", width=5)
        
        # --- Text and Progress Bar Logic ---
        
        # Load fonts (Use try-except block to handle missing font files)
        try:
            arial = ImageFont.truetype("EsproMusic/assets/font2.ttf", 30)
            font_title = ImageFont.truetype("EsproMusic/assets/font.ttf", 40) # Larger font for main title
            font_meta = ImageFont.truetype("EsproMusic/assets/font2.ttf", 25) # Smaller font for metadata
        except IOError:
            print("Font files not found. Using default font.")
            arial = ImageFont.load_default()
            font_title = ImageFont.load_default()
            font_meta = ImageFont.load_default()
        
        
        # 1. App Name (Top-left, inside the frame)
        draw.text((x_offset + 5, y_offset + 5), unidecode(app.name), fill="white", font=font_meta)
        
        # 2. Main Title - Below the frame
        title_text = clear(title)
        title_w, title_h = draw.textsize(title_text, font=font_title)
        
        # Y-coordinate: 10px below the frame's bottom edge (y_offset + img_h + 10)
        draw.text(
            (x_offset, y_offset + img_h + 10), 
            title_text,
            (255, 255, 255),
            font=font_title,
        )

        # 3. Channel and Views (Metadata) - Below the title
        metadata_text = f"{channel} | {views[:23]}"
        # Y-coordinate: 5px below the title
        metadata_y = y_offset + img_h + title_h + 15
        draw.text(
            (x_offset, metadata_y), 
            metadata_text,
            (255, 255, 255),
            font=font_meta,
        )
        
        # 4. Progress Bar Line (Near the very bottom of the screen)
        progress_line_y = 700 
        draw.line(
            [(55, progress_line_y), (1220, progress_line_y)],
            fill="white",
            width=5,
            joint="curve",
        )
        
        # 5. Progress Ellipse
        draw.ellipse(
            [(918, progress_line_y - 12), (942, progress_line_y + 12)], 
            outline="white",
            fill="white",
            width=15,
        )
        
        # 6. Timestamps (Below the progress bar)
        timestamp_y = progress_line_y + 10
        
        # Left timestamp (00:00)
        draw.text(
            (36, timestamp_y), 
            "00:00",
            (255, 255, 255),
            font=font_meta,
        )
        
        # Right timestamp (Duration) - Right Align
        duration_text = f"{duration[:23]}"
        duration_w, _ = draw.textsize(duration_text, font=font_meta)
        draw.text(
            (1220 - duration_w, timestamp_y), 
            duration_text,
            (255, 255, 255),
            font=font_meta,
        )
        
        # 7. Save the thumbnail
        try:
            os.remove(f"cache/thumb{videoid}.png")
        except Exception:
            pass
        
        background.save(f"cache/{videoid}.png")
        return f"cache/{videoid}.png"
        
    except Exception as e:
        print(f"An error occurred: {e}")
        # Return default YouTube image URL on failure
        return YOUTUBE_IMG_URL
