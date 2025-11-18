import asyncio import importlib

from pyrogram import idle from pytgcalls.exceptions import NoActiveGroupCall

import config from EsproMusic import LOGGER, app, userbot from EsproMusic.core.call import Ritik from EsproMusic.misc import sudo from EsproMusic.plugins import ALL_MODULES from EsproMusic.utils.database import get_banned_users, get_gbanned from config import BANNED_USERS

async def init(): # Check for assistant session strings if ( not config.STRING1 and not config.STRING2 and not config.STRING3 and not config.STRING4 and not config.STRING5 ): LOGGER(name).error("Assistant client variables not defined, exiting...") exit()

# Sudo users load
await sudo()

# Load banned users
try:
    users = await get_gbanned()
    for user_id in users:
        BANNED_USERS.add(user_id)

    users = await get_banned_users()
    for user_id in users:
        BANNED_USERS.add(user_id)
except:
    pass

# Start bot
await app.start()

# Import all modules
for all_module in ALL_MODULES:
    try:
        importlib.import_module(f"EsproMusic.plugins.{all_module}")
        LOGGER("EsproMusic.plugins").info(f"Imported -> {all_module}")
    except Exception as e:
        LOGGER("EsproMusic.plugins").error(f"Failed to import {all_module}: {e}")

LOGGER("EsproMusic.plugins").info("Successfully Imported All Modules...")

await userbot.start()
await Ritik.start()

# Start stream call for activation
try:
    await Ritik.stream_call("https://te.legra.ph/file/29f784eb49d230ab62e9e.mp4")
except NoActiveGroupCall:
    LOGGER("EsproMusic").error(
        "Please turn on the videochat of your log group/channel.\n\nStopping Bot..."
    )
    exit()
except:
    pass

await Ritik.decorators()

LOGGER("EsproMusic").info(
    "EsproMusicBot Started Successfully!\n\nYaha app ko nahi aana hai, apni girlfriend jo bhej sakte hai @Esprosupport"
)

await idle()

# Stop everything on shutdown
await app.stop()
await userbot.stop()

LOGGER("EsproMusic").info("Stopping Espro Music Bot...")

if name == "main": asyncio.get_event_loop().run_until_complete(init())
