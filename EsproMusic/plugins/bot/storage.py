from pyrogram.types import Message
from pyrogram.errors import MessageNotModified

from config import PRIVATE_STORAGE_CHANNEL

async def search_song_in_channel(app, title: str, is_video: bool):
    async for msg in app.search_messages(PRIVATE_STORAGE_CHANNEL, query=title, filter="video" if is_video else "audio"):
        if msg and (msg.video or msg.audio):
            return msg
    return None

async def save_song_to_channel(app, file_msg: Message, caption: str = None):
    try:
        sent = await file_msg.copy(chat_id=PRIVATE_STORAGE_CHANNEL, caption=caption)
        return sent
    except Exception as e:
        print(f"Error saving to channel: {e}")
        return None
