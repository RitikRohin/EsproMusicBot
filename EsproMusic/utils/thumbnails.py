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
    widthRatio = maxWidth / image.size[0]
    heightRatio = maxHeight / image.size[1]
    newWidth = int(widthRatio * image.size[0])
    newHeight = int(heightRatio * image.size[1])
    newImage = image.resize((newWidth, newHeight))
    return newImage


def clear(text):
    list = text.split(" ")
    title = ""
    for i in list:
        if len(title) + len(i) < 60:
            title += " " + i
    return title.strip()


async def gen_thumb(videoid):
    if os.path.isfile(f"cache/{videoid}.png"):
        return f"cache/{videoid}.png"

    url = f"https://www.youtube.com/watch?v={videoid}"
    try:
        results = VideosSearch(url, limit=1)
        for result in (await results.next())["result"]:
            try:
                title = result["title"]
                title = re.sub("\W+", " ", title)
                title = title.title()
            except:
                title = "Unsupported Title"
            try:
                duration = result["duration"]
            except:
                duration = "Unknown Mins"
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            try:
                views = result["viewCount"]["short"]
            except:
                views = "Unknown Views"
            try:
                channel = result["channel"]["name"]
            except:
                channel = "Unknown Channel"

        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                if resp.status == 200:
                    f = await aiofiles.open(f"cache/thumb{videoid}.png", mode="wb")
                    await f.write(await resp.read())
                    await f.close()

        youtube = Image.open(f"cache/thumb{videoid}.png")
        image1 = changeImageSize(1280, 720, youtube)
        image2 = image1.convert("RGBA")
        
        # 1. बैकग्राउंड को ब्लर और डार्क करें
        background = image2.filter(filter=ImageFilter.BoxBlur(10))
        enhancer = ImageEnhance.Brightness(background)
        background = enhancer.enhance(0.5)
        
        # --- कस्टमाइज़्ड राउंडेड रेक्टेंगल फ़्रेम लॉजिक ---
        
        # फ़्रेम के अंदर की इमेज का साइज़ (1280x720 कैनवस पर केंद्रित)
        img_w, img_h = 1180, 640
        x_offset = (1280 - img_w) // 2 
        y_offset = (720 - img_h) // 2 
        
        # 2. इनर इमेज (Inner Image) तैयार करें
        framed_image = changeImageSize(img_w, img_h, youtube)
        
        # 3. राउंडेड रेक्टेंगल मास्क (Rounded Rectangle Mask) बनाएं
        radius = 30 # कॉर्नर रेडियस
        img_mask = Image.new('L', (img_w, img_h), 0)
        img_draw_mask = ImageDraw.Draw(img_mask)
        
        # मास्क पर राउंडेड रेक्टेंगल शेप बनाएं
        img_draw_mask.rectangle([(0, radius), (img_w, img_h - radius)], fill=255)
        img_draw_mask.rectangle([(radius, 0), (img_w - radius, img_h)], fill=255)
        img_draw_mask.ellipse((0, 0, radius * 2, radius * 2), fill=255) # Top-left
        img_draw_mask.ellipse((img_w - radius * 2, 0, img_w, radius * 2), fill=255) # Top-right
        img_draw_mask.ellipse((0, img_h - radius * 2, radius * 2, img_h), fill=255) # Bottom-left
        img_draw_mask.ellipse((img_w - radius * 2, img_h - radius * 2, img_w, img_h), fill=255) # Bottom-right
        
        # 4. फ्रेम्ड इमेज को बैकग्राउंड पर पेस्ट करें (मास्क का उपयोग करके)
        background.paste(framed_image, (x_offset, y_offset), img_mask)
        
        # 5. सफ़ेद बॉर्डर (White Border) बनाएं
        # बॉर्डर के निर्देशांक: इनर इमेज के चारों ओर 5px मार्जिन (45, 35, 1235, 685)
        draw = ImageDraw.Draw(background)
        border_radius = radius + 3 # बॉर्डर के लिए थोड़ा बड़ा रेडियस
        draw.rounded_rectangle((x_offset - 5, y_offset - 5, x_offset + img_w + 5, y_offset + img_h + 5), radius=border_radius, outline="white", width=5)
        
        # --- टेक्स्ट और प्रोग्रेस बार लॉजिक (फ़्रेम पर ओवरले) ---
        
        arial = ImageFont.truetype("EsproMusic/assets/font2.ttf", 30) # छोटे टेक्स्ट के लिए
        font = ImageFont.truetype("EsproMusic/assets/font.ttf", 45) # मुख्य शीर्षक के लिए
        
        # 1. ऐप का नाम (ऊपर-बाएं, मूल कोड में यह ऊपर-दाएं था, मैंने इसे ऊपर-बाएं कर दिया है जैसा कि अरिजीत सिंह के उदाहरण में है)
        draw.text((36, 8), unidecode(app.name), fill="white", font=arial)
        
        # 2. मुख्य शीर्षक (Main Title) - फ़्रेम के नीचे की ओर ओवरले
        # Y-कोऑर्डिनेट को एडजस्ट किया गया है ताकि यह फ़्रेम के नीचे ठीक से बैठे
        title_text = clear(title)
        title_w, title_h = draw.textsize(title_text, font=font)
        draw.text(
            (x_offset, y_offset + img_h + 10), # फ़्रेम के नीचे 10px का गैप
            title_text,
            (255, 255, 255),
            font=font,
        )

        # 3. चैनल और व्यूज़ - शीर्षक के नीचे
        channel_views_text = f"{channel} | {views[:23]}"
        draw.text(
            (x_offset, y_offset + img_h + title_h + 20), # शीर्षक के नीचे 20px का गैप
            channel_views_text,
            (255, 255, 255),
            font=arial,
        )
        
        # 4. प्रोग्रेस बार लाइन (स्क्रीन के सबसे नीचे)
        progress_line_y = 660 
        draw.line(
            [(55, progress_line_y), (1220, progress_line_y)],
            fill="white",
            width=5,
            joint="curve",
        )
        
        # 5. प्रोग्रेस एलिप्स (Ellipse)
        draw.ellipse(
            [(918, progress_line_y - 12), (942, progress_line_y + 12)], # लाइन पर केंद्रित
            outline="white",
            fill="white",
            width=15,
        )
        
        # 6. टाइमस्टैम्प्स (प्रोग्रेस बार के नीचे)
        draw.text(
            (36, progress_line_y + 25), # लाइन के नीचे 25px का गैप
            "00:00",
            (255, 255, 255),
            font=arial,
        )
        draw.text(
            (1185 - draw.textsize(f"{duration[:23]}", font=arial)[0], progress_line_y + 25), # दाएं अलाइन
            f"{duration[:23]}",
            (255, 255, 255),
            font=arial,
        )
        
        # --- कोड अंत ---
        
        try:
            os.remove(f"cache/thumb{videoid}.png")
        except:
            pass
        background.save(f"cache/{videoid}.png")
        return f"cache/{videoid}.png"
    except Exception as e:
        print(e)
        return YOUTUBE_IMG_URL
