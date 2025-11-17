import os
from random import randint
from typing import Union

from pyrogram.types import InlineKeyboardMarkup

import config
from EsproMusic import Carbon, YouTube, app
from EsproMusic.core.call import Ritik
from EsproMusic.misc import db
from EsproMusic.utils.database import add_active_video_chat, is_active_chat
from EsproMusic.utils.exceptions import AssistantErr
from EsproMusic.utils.inline import aq_markup, close_markup, stream_markup
from EsproMusic.utils.pastebin import RitikBin
from EsproMusic.utils.stream.queue import put_queue, put_queue_index
from EsproMusic.utils.thumbnails import gen_thumb

# 🔥 नया: लास्ट क्यू मैसेज ID को स्टोर करने के लिए एक सिंपल इन-मेमोरी डिक्शनरी
# नोट: आपको इस डिक्शनरी को बॉट के ग्लोबल स्कोप (main file) में परिभाषित करना होगा
# ताकि यह फंक्शन कॉल्स के बीच डेटा को याद रख सके।
LAST_QUEUE_MSG = {} 

async def delete_message_safely(chat_id, message_id):
    """Safely deletes a message by its ID."""
    if message_id:
        try:
            await app.delete_messages(chat_id, message_id)
        except Exception:
            pass

async def stream(
    _,
    mystic,
    user_id,
    result,
    chat_id,
    user_name,
    original_chat_id,
    video: Union[bool, str] = None,
    streamtype: Union[bool, str] = None,
    spotify: Union[bool, str] = None,
    forceplay: Union[bool, str] = None,
):
    if not result:
        return
    if forceplay:
        await Ritik.force_stop_stream(chat_id)

    # ------------------------------------------------------------------------
    # [1] PLAYLIST STREAM
    # ------------------------------------------------------------------------
    if streamtype == "playlist":
        msg = f"{_['play_19']}\n\n"
        count = 0
        for search in result:
            if int(count) == config.PLAYLIST_FETCH_LIMIT:
                continue
            try:
                (
                    title,
                    duration_min,
                    duration_sec,
                    thumbnail,
                    vidid,
                ) = await YouTube.details(search, False if spotify else True)
            except:
                continue
            if str(duration_min) == "None":
                continue
            if duration_sec > config.DURATION_LIMIT:
                continue
            if await is_active_chat(chat_id):
                await put_queue(
                    chat_id,
                    original_chat_id,
                    f"vid_{vidid}",
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "video" if video else "audio",
                )
                position = len(db.get(chat_id)) - 1
                count += 1
                msg += f"{count}. {title[:70]}\n"
                msg += f"{_['play_20']} {position}\n\n"
            else:
                # 🔥 DELETE OLD COMMAND MESSAGE
                await delete_message_safely(original_chat_id, mystic.id if mystic else None)
                
                if not forceplay:
                    db[chat_id] = []
                status = True if video else None
                try:
                    file_path, direct = await YouTube.download(
                        vidid, mystic, video=status, videoid=True
                    )
                except:
                    raise AssistantErr(_["play_14"])
                await Ritik.join_call(
                    chat_id,
                    original_chat_id,
                    file_path,
                    video=status,
                    image=thumbnail,
                )
                await put_queue(
                    chat_id,
                    original_chat_id,
                    file_path if direct else f"vid_{vidid}",
                    title,
                    duration_min,
                    user_name,
                    vidid,
                    user_id,
                    "video" if video else "audio",
                    forceplay=forceplay,
                )
                img = await gen_thumb(vidid)
                button = stream_markup(_, chat_id)
                run = await app.send_photo(
                    original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{vidid}",
                        title[:23],
                        duration_min,
                        user_name,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                    has_spoiler=True
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"
        if count == 0:
            return
        else:
            link = await RitikBin(msg)
            lines = msg.count("\n")
            if lines >= 17:
                car = os.linesep.join(msg.split(os.linesep)[:17])
            else:
                car = msg
            carbon = await Carbon.generate(car, randint(100, 10000000))
            upl = close_markup(_)
            return await app.send_photo(
                original_chat_id,
                photo=carbon,
                caption=_["play_21"].format(position, link),
                reply_markup=upl,
            )
            
    # ------------------------------------------------------------------------
    # [2] YOUTUBE STREAM
    # ------------------------------------------------------------------------
    elif streamtype == "youtube":
        link = result["link"]
        vidid = result["vidid"]
        title = (result["title"]).title()
        duration_min = result["duration_min"]
        thumbnail = result["thumb"]
        status = True if video else None
        try:
            file_path, direct = await YouTube.download(
                vidid, mystic, videoid=True, video=status
            )
        except:
            raise AssistantErr(_["play_14"])
            
        if await is_active_chat(chat_id):
            # Q में मैसेज भेजा जा रहा है
            await put_queue(
                chat_id,
                original_chat_id,
                file_path if direct else f"vid_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            
            queue_msg = await app.send_message(
                chat_id=original_chat_id,
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
            # 🔥 Q MESSAGE ID STORE करें
            LAST_QUEUE_MSG[original_chat_id] = queue_msg.id
            
        else:
            # 🔥 OLD Q MESSAGE DELETE करें
            old_queue_id = LAST_QUEUE_MSG.pop(original_chat_id, None)
            await delete_message_safely(original_chat_id, old_queue_id)
            
            # 🔥 OLD COMMAND MESSAGE DELETE करें
            await delete_message_safely(original_chat_id, mystic.id if mystic else None)
            
            if not forceplay:
                db[chat_id] = []
            await Ritik.join_call(
                chat_id,
                original_chat_id,
                file_path,
                video=status,
                image=thumbnail,
            )
            await put_queue(
                chat_id,
                original_chat_id,
                file_path if direct else f"vid_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if video else "audio",
                forceplay=forceplay,
            )
            img = await gen_thumb(vidid)
            button = stream_markup(_, chat_id)
            run = await app.send_photo(
                original_chat_id,
                photo=img,
                caption=_["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{vidid}",
                    title[:23],
                    duration_min,
                    user_name,
                ),
                reply_markup=InlineKeyboardMarkup(button),
                has_spoiler=True
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"
            
    # ------------------------------------------------------------------------
    # [3] SOUNDCLOUD STREAM
    # ------------------------------------------------------------------------
    elif streamtype == "soundcloud":
        file_path = result["filepath"]
        title = result["title"]
        duration_min = result["duration_min"]
        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            queue_msg = await app.send_message(
                chat_id=original_chat_id,
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
            # 🔥 Q MESSAGE ID STORE करें
            LAST_QUEUE_MSG[original_chat_id] = queue_msg.id
        else:
            # 🔥 OLD Q MESSAGE DELETE करें
            old_queue_id = LAST_QUEUE_MSG.pop(original_chat_id, None)
            await delete_message_safely(original_chat_id, old_queue_id)
            
            # 🔥 OLD COMMAND MESSAGE DELETE करें
            await delete_message_safely(original_chat_id, mystic.id if mystic else None)

            if not forceplay:
                db[chat_id] = []
            await Ritik.join_call(chat_id, original_chat_id, file_path, video=None)
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "audio",
                forceplay=forceplay,
            )
            button = stream_markup(_, chat_id)
            run = await app.send_photo(
                original_chat_id,
                photo=config.SOUNCLOUD_IMG_URL,
                caption=_["stream_1"].format(
                    config.SUPPORT_CHAT, title[:23], duration_min, user_name
                ),
                reply_markup=InlineKeyboardMarkup(button),
                has_spoiler=True
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
            
    # ------------------------------------------------------------------------
    # [4] TELEGRAM STREAM
    # ------------------------------------------------------------------------
    elif streamtype == "telegram":
        file_path = result["path"]
        link = result["link"]
        title = (result["title"]).title()
        duration_min = result["dur"]
        status = True if video else None
        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "video" if video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            queue_msg = await app.send_message(
                chat_id=original_chat_id,
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
            # 🔥 Q MESSAGE ID STORE करें
            LAST_QUEUE_MSG[original_chat_id] = queue_msg.id
        else:
            # 🔥 OLD Q MESSAGE DELETE करें
            old_queue_id = LAST_QUEUE_MSG.pop(original_chat_id, None)
            await delete_message_safely(original_chat_id, old_queue_id)
            
            # 🔥 OLD COMMAND MESSAGE DELETE करें
            await delete_message_safely(original_chat_id, mystic.id if mystic else None)

            if not forceplay:
                db[chat_id] = []
            await Ritik.join_call(chat_id, original_chat_id, file_path, video=status)
            await put_queue(
                chat_id,
                original_chat_id,
                file_path,
                title,
                duration_min,
                user_name,
                streamtype,
                user_id,
                "video" if video else "audio",
                forceplay=forceplay,
            )
            if video:
                await add_active_video_chat(chat_id)
            button = stream_markup(_, chat_id)
            run = await app.send_photo(
                original_chat_id,
                photo=config.TELEGRAM_VIDEO_URL if video else config.TELEGRAM_AUDIO_URL,
                caption=_["stream_1"].format(link, title[:23], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
                has_spoiler=True
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
            
    # ------------------------------------------------------------------------
    # [5] LIVE STREAM
    # ------------------------------------------------------------------------
    elif streamtype == "live":
        link = result["link"]
        vidid = result["vidid"]
        title = (result["title"]).title()
        thumbnail = result["thumb"]
        duration_min = "Live Track"
        status = True if video else None
        if await is_active_chat(chat_id):
            await put_queue(
                chat_id,
                original_chat_id,
                f"live_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            queue_msg = await app.send_message(
                chat_id=original_chat_id,
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
            # 🔥 Q MESSAGE ID STORE करें
            LAST_QUEUE_MSG[original_chat_id] = queue_msg.id
        else:
            # 🔥 OLD Q MESSAGE DELETE करें
            old_queue_id = LAST_QUEUE_MSG.pop(original_chat_id, None)
            await delete_message_safely(original_chat_id, old_queue_id)
            
            # 🔥 OLD COMMAND MESSAGE DELETE करें
            await delete_message_safely(original_chat_id, mystic.id if mystic else None)

            if not forceplay:
                db[chat_id] = []
            n, file_path = await YouTube.video(link)
            if n == 0:
                raise AssistantErr(_["str_3"])
            await Ritik.join_call(
                chat_id,
                original_chat_id,
                file_path,
                video=status,
                image=thumbnail if thumbnail else None,
            )
            await put_queue(
                chat_id,
                original_chat_id,
                f"live_{vidid}",
                title,
                duration_min,
                user_name,
                vidid,
                user_id,
                "video" if video else "audio",
                forceplay=forceplay,
            )
            img = await gen_thumb(vidid)
            button = stream_markup(_, chat_id)
            run = await app.send_photo(
                original_chat_id,
                photo=img,
                caption=_["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{vidid}",
                    title[:23],
                    duration_min,
                    user_name,
                ),
                reply_markup=InlineKeyboardMarkup(button),
                has_spoiler=True
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
            
    # ------------------------------------------------------------------------
    # [6] INDEX STREAM
    # ------------------------------------------------------------------------
    elif streamtype == "index":
        link = result
        title = "ɪɴᴅᴇx ᴏʀ ᴍ3ᴜ8 ʟɪɴᴋ"
        duration_min = "00:00"
        if await is_active_chat(chat_id):
            await put_queue_index(
                chat_id,
                original_chat_id,
                "index_url",
                title,
                duration_min,
                user_name,
                link,
                "video" if video else "audio",
            )
            position = len(db.get(chat_id)) - 1
            button = aq_markup(_, chat_id)
            
            # Note: Index stream uses edit_text for queue notification, which returns a Message object
            queue_msg = await mystic.edit_text(
                text=_["queue_4"].format(position, title[:27], duration_min, user_name),
                reply_markup=InlineKeyboardMarkup(button),
            )
            # 🔥 Q MESSAGE ID STORE करें
            LAST_QUEUE_MSG[original_chat_id] = queue_msg.id
            
        else:
            # 🔥 OLD Q MESSAGE DELETE करें
            old_queue_id = LAST_QUEUE_MSG.pop(original_chat_id, None)
            await delete_message_safely(original_chat_id, old_queue_id)
            
            # 🔥 OLD COMMAND MESSAGE DELETE करें (mystic को यहाँ delete किया जा रहा है)
            # चूंकि ऊपर edit_text का उपयोग किया गया था, इसलिए mystic अब queue message बन गया होगा।
            # हम सिर्फ़ old_queue_id पर भरोसा करेंगे।

            if not forceplay:
                db[chat_id] = []
            await Ritik.join_call(
                chat_id,
                original_chat_id,
                link,
                video=True if video else None,
            )
            await put_queue_index(
                chat_id,
                original_chat_id,
                "index_url",
                title,
                duration_min,
                user_name,
                link,
                "video" if video else "audio",
                forceplay=forceplay,
            )
            button = stream_markup(_, chat_id)
            run = await app.send_photo(
                original_chat_id,
                photo=config.STREAM_IMG_URL,
                caption=_["stream_2"].format(user_name),
                reply_markup=InlineKeyboardMarkup(button),
                has_spoiler=True
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"
            # original command/queue message को delete करें
            await delete_message_safely(original_chat_id, mystic.id if mystic else None)

