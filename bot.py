import os
import math
import asyncio
import tempfile
import logging
from typing import Dict, List
from collections import defaultdict
from datetime import datetime, timedelta
from dotenv import load_dotenv

from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# --- Credentials ---
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Spotify client
spotify_client = Spotify(
    client_credentials_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET
    )
)

search_results: Dict[int, List[dict]] = defaultdict(list)
current_page: Dict[int, int] = defaultdict(lambda: 1)
queries: Dict[int, str] = {}
recent_queries: Dict[int, List[str]] = defaultdict(list)
last_download_time: Dict[int, datetime] = defaultdict(lambda: datetime.min)
result_message_id: Dict[int, int] = {}
result_photo_id: Dict[int, int] = {}

ITEMS_PER_PAGE = 5
DOWNLOAD_COOLDOWN = timedelta(seconds=30)
SPOTDL_TIMEOUT = 60  # seconds

def send_typing_action(func):
    async def command_func(update, context, *args, **kwargs):
        chat_id = update.effective_chat.id
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        return await func(update, context, *args, **kwargs)
    return command_func


@send_typing_action
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🎵 *Welcome to LyricCraft Spotify Downloader!*\n"
        "Search for songs and download them as MP3.\n\n"
        "Commands:\n"
        "/start - Show welcome message\n"
        "/help - Show usage instructions\n"
        "/recent - Show your last 5 searches\n\n"
        "_Created with ❤️ by Lokesh.R_",
        parse_mode=ParseMode.MARKDOWN,
    )

@send_typing_action
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📖 *How to use the bot:*\n\n"
        "1. Send a song name to search.\n"
        "2. Browse pages of tracks.\n"
        "3. Click the track button to download individual songs.\n"
        "4. Or click \"Download This Page\" to download all songs on the current page.\n"
        "5. Use /recent to see your recent searches.\n\n"
        "_Please wait 30 seconds between downloads._",
        parse_mode=ParseMode.MARKDOWN,
    )

@send_typing_action
async def recent_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    recent = recent_queries.get(chat_id, [])
    if not recent:
        msg = "😕 You have no recent searches yet."
    else:
        msg = "🕘 Your recent searches:\n" + "\n".join(f"- {q}" for q in recent[-5:])
    await update.message.reply_text(msg)

@send_typing_action
async def search_and_display(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat.id
    query = update.message.text.strip()
    if not query:
        await update.message.reply_text("❗ Please provide a search term.")
        return

    if query not in recent_queries[chat_id]:
        recent_queries[chat_id].append(query)
        if len(recent_queries[chat_id]) > 20:
            recent_queries[chat_id].pop(0)
    await display_search_results(chat_id, query, context, page=1)

async def _schedule_message_delete(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, delay: int = 60):
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id, message_id)
        logger.debug(f"Deleted message {message_id} in chat {chat_id}")
    except Exception as e:
        logger.warning(f"Failed to delete message {message_id}: {e}")

async def display_search_results(
        chat_id: int, query: str, context: ContextTypes.DEFAULT_TYPE, page: int = 1
) -> None:
    try:
        results = spotify_client.search(q=query, type="track", limit=50)
        tracks = results.get("tracks", {}).get("items", [])

        if not tracks:
            await context.bot.send_message(chat_id, "❌ No results found.")
            return

        search_results[chat_id] = tracks
        current_page[chat_id] = page
        queries[chat_id] = query

        total_tracks = len(tracks)
        total_pages = max(1, math.ceil(total_tracks / ITEMS_PER_PAGE))
        page = max(1, min(page, total_pages))
        start = (page - 1) * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        poster_url = None
        if tracks and tracks[0]["album"]["images"]:
            poster_url = tracks[0]["album"]["images"][0]["url"]

        for dct in [result_message_id, result_photo_id]:
            if chat_id in dct:
                try:
                    await context.bot.delete_message(chat_id, dct[chat_id])
                except Exception:
                    pass
                dct.pop(chat_id, None)

        if poster_url:
            try:
                photo_msg = await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=poster_url,
                    caption=f"🎧 *Results for:* `{query}` (Page {page}/{total_pages})",
                    parse_mode=ParseMode.MARKDOWN,
                )
                context.application.create_task(_schedule_message_delete(context, chat_id, photo_msg.message_id, 60))
                result_photo_id[chat_id] = photo_msg.message_id
            except Exception as e:
                logger.warning(f"Could not send photo: {e}")

        keyboard = []
        def format_duration(ms: int) -> str:
            seconds = ms // 1000
            minutes, sec = divmod(seconds, 60)
            return f"{minutes}:{sec:02}"
        for idx, track in enumerate(tracks[start:end], start=start):
            name = track["name"]
            artists = ", ".join(a["name"] for a in track["artists"])
            duration = format_duration(track.get("duration_ms", 0))
            text = f"{name} — {artists} [{duration}]"
            keyboard.append([InlineKeyboardButton(text, callback_data=f"track_{idx}")])

        nav_buttons = []
        if page > 1:
            nav_buttons.append(InlineKeyboardButton("⬅️ Back", callback_data="prev_page"))
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data="next_page"))
        if nav_buttons:
            keyboard.append(nav_buttons)
        keyboard.append([InlineKeyboardButton("⬇️ Download This Page", callback_data="download_page")])

        try:
            msg = await context.bot.send_message(
                chat_id=chat_id,
                text="📍 *Choose a track to download or download the entire page:*",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
            result_message_id[chat_id] = msg.message_id
            context.application.create_task(_schedule_message_delete(context, chat_id, msg.message_id, 60))
        except Exception as e:
            logger.error(f"Error when sending result message: {e}")

    except Exception as e:
        logger.error(f"Error displaying search results: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id, f"⚠️ Error: `{e}`", parse_mode=ParseMode.MARKDOWN
        )

async def handle_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    if chat_id not in current_page or chat_id not in queries:
        await query.message.reply_text("❗ Session expired. Please search again.")
        return

    if query.data == "next_page":
        current_page[chat_id] += 1
    elif query.data == "prev_page":
        current_page[chat_id] -= 1

    total_tracks = len(search_results.get(chat_id, []))
    total_pages = max(1, math.ceil(total_tracks / ITEMS_PER_PAGE))
    current_page[chat_id] = max(1, min(current_page[chat_id], total_pages))

    await display_search_results(chat_id, queries[chat_id], context, current_page[chat_id])

async def select_song(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id

    now = datetime.utcnow()
    if now - last_download_time[chat_id] < DOWNLOAD_COOLDOWN:
        wait_time = int((DOWNLOAD_COOLDOWN - (now - last_download_time[chat_id])).total_seconds())
        await query.message.reply_text(f"⏳ Please wait {wait_time} seconds before downloading again.")
        return
    last_download_time[chat_id] = now

    if chat_id not in search_results:
        await query.message.reply_text("❗ Session expired. Please search again.")
        return

    try:
        track_index = int(query.data.split("_")[1])
        track = search_results[chat_id][track_index]
        track_name = track["name"]
        artist = ", ".join(a["name"] for a in track["artists"])
        track_url = track["external_urls"]["spotify"]

        await query.edit_message_text(
            f"🎶 Selected: *{track_name}* by *{artist}*\n\n⏳ Downloading...",
            parse_mode=ParseMode.MARKDOWN,
        )
        await download_and_send_audio(chat_id, track_url, track_name, artist, context, query_message=query.message)
    except Exception as e:
        logger.error(f"Error in select_song: {e}", exc_info=True)
        await query.message.reply_text(
            f"⚠️ Error: {e}\n\n_Created with ❤️ by Lokesh.R_", parse_mode=ParseMode.MARKDOWN
        )


async def download_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id

    now = datetime.utcnow()
    if now - last_download_time[chat_id] < DOWNLOAD_COOLDOWN:
        wait_time = int((DOWNLOAD_COOLDOWN - (now - last_download_time[chat_id])).total_seconds())
        await query.message.reply_text(f"⏳ Please wait {wait_time} seconds before downloading again.")
        return
    last_download_time[chat_id] = now

    if chat_id not in search_results or chat_id not in current_page:
        await query.message.reply_text("❗ Session expired. Please search again.")
        return

    tracks = search_results[chat_id]
    page = current_page[chat_id]
    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    page_tracks = tracks[start:end]

    await query.edit_message_text(
        f"⬇️ Downloading all songs on page {page}...\n\n⏳ Please wait...",
        parse_mode=ParseMode.MARKDOWN,
    )

    for track in page_tracks:
        track_name = track["name"]
        artist = ", ".join(a["name"] for a in track["artists"])
        track_url = track["external_urls"]["spotify"]
        caption = (
            f"✅ *Downloaded: {track_name}*\n"
            f"👤 *Artist:* {artist}\n\n"
            "_Thanks for using LyricCraft! ❤️ Created by Lokesh.R_"
        )
        try:
            await download_and_send_audio(
                chat_id, track_url, track_name, artist, context, caption_override=caption, query_message=query.message
            )
        except Exception as e:
            logger.error(f"Failed to download/send track {track_name}: {e}")

    await query.message.reply_text("✔️ Finished downloading all songs on this page.")

def find_mp3_file(directory):
    """Recursively search for the first MP3 file in a directory."""
    for root, dirs, files in os.walk(directory):
        for f in files:
            if f.lower().endswith('.mp3'):
                return os.path.join(root, f)
    return None

async def download_and_send_audio(
    chat_id,
    spotify_url,
    title,
    performer,
    context,
    caption_override: str = None,
    query_message=None
) -> None:
    try:
        with tempfile.TemporaryDirectory() as tmpdirname:
            logger.info(f"Downloading to temp dir: {tmpdirname}")

            command = ["spotdl", "download", spotify_url, "--output", tmpdirname]
            try:
                process = await asyncio.wait_for(
                    asyncio.create_subprocess_exec(
                        *command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    ),
                    timeout=5  # For process *creation*
                )
            except asyncio.TimeoutError:
                logger.error("spotdl did not start in time")
                msg = "❌ Download setup timed out."
                if query_message:
                    await query_message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
                else:
                    await context.bot.send_message(chat_id, msg, parse_mode=ParseMode.MARKDOWN)
                return

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=SPOTDL_TIMEOUT)
            except asyncio.TimeoutError:
                process.kill()
                msg = "❌ Download timed out after 60 seconds."
                if query_message:
                    await query_message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
                else:
                    await context.bot.send_message(chat_id, msg, parse_mode=ParseMode.MARKDOWN)
                return

            if process.returncode != 0:
                stderr_text = stderr.decode()
                logger.error(f"spotdl error: {stderr_text}")
                outmsg = f"❌ Download failed:\n`{stderr_text}`"
                if query_message:
                    await query_message.reply_text(outmsg, parse_mode=ParseMode.MARKDOWN)
                else:
                    await context.bot.send_message(
                        chat_id, outmsg, parse_mode=ParseMode.MARKDOWN
                    )
                return

            mp3_path = find_mp3_file(tmpdirname)
            if not mp3_path:
                logger.error(
                    "MP3 not found in %s. spotDL stdout:\n%s\nstderr:\n%s",
                    tmpdirname, stdout.decode(), stderr.decode()
                )
                msg = "❌ Download failed. No MP3 file found. (Check log for spotDL output.)"
                if query_message:
                    await query_message.reply_text(msg)
                else:
                    await context.bot.send_message(chat_id, msg)
                return

            with open(mp3_path, "rb") as audio_file:
                try:
                    await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=audio_file,
                        title=title,
                        performer=performer,
                        caption=caption_override or "✅ *Downloaded successfully!*\n_Created with ❤️ by Lokesh.R_",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception as e:
                    logger.error(f"Telegram send_audio failed: {e}")
                    msg = "⚠️ Error sending audio to Telegram."
                    if query_message:
                        await query_message.reply_text(msg)
                    else:
                        await context.bot.send_message(chat_id, msg)

    except Exception as e:
        logger.error(f"Error sending audio: {e}", exc_info=True)
        msg = f"⚠️ Error occurred: {e}"
        if query_message:
            await query_message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        else:
            await context.bot.send_message(chat_id, msg, parse_mode=ParseMode.MARKDOWN)

def main() -> None:
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("recent", recent_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_and_display))
    app.add_handler(CallbackQueryHandler(handle_pagination, pattern="prev_page|next_page"))
    app.add_handler(CallbackQueryHandler(select_song, pattern="track_.*"))
    app.add_handler(CallbackQueryHandler(download_page, pattern="download_page"))
    logger.info("🤖 Bot running... Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()