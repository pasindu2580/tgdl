import os
import math
import psutil
import logging
import platform
from time import time
from asyncio import sleep, get_event_loop
from PIL import Image
from os import path as ospath
from datetime import datetime
from urllib.parse import urlparse
from moviepy.video.io.VideoFileClip import VideoFileClip
from pyrogram.errors import BadRequest
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from colab_leecher import colab_bot
from colab_leecher.utility.variables import (
    BOT,
    MSG,
    BotTimes,
    Messages,
    Paths,
)


def isLink(_, __, update):
    if update.text:
        if "/content/" in str(update.text) or "/home" in str(update.text):
            return True
        elif update.text.startswith("magnet:?xt=urn:btih:"):
            return True

        parsed = urlparse(update.text)

        if parsed.scheme in ("http", "https") and parsed.netloc:
            return True

    return False


def is_google_drive(link):
    return "drive.google.com" in link

def is_mega(link):
    return "mega.nz" in link

def is_terabox(link):
    return "terabox" in link or "1024tera" in link

def is_ytdl_link(link):
    return "youtube.com" in link or "youtu.be" in link

def is_telegram(link):
    return "t.me" in link

def is_torrent(link):
    return "magnet" in link or "torrent" in link


def getTime(seconds):
    seconds = int(seconds)
    days = seconds // (24 * 3600)
    seconds = seconds % (24 * 3600)
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60

    if days > 0:
        return f"{days}d {hours}h {minutes}m {seconds}s"
    elif hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"


def sizeUnit(size):
    if size > 1024 * 1024 * 1024 * 1024 * 1024:
        siz = f"{size/(1024**5):.2f} PiB"
    elif size > 1024 * 1024 * 1024 * 1024:
        siz = f"{size/(1024**4):.2f} TiB"
    elif size > 1024 * 1024 * 1024:
        siz = f"{size/(1024**3):.2f} GiB"
    elif size > 1024 * 1024:
        siz = f"{size/(1024**2):.2f} MiB"
    elif size > 1024:
        siz = f"{size/1024:.2f} KiB"
    else:
        siz = f"{size:.2f} B"
    return siz


def fileType(file_path: str):
    extensions_dict = {
        ".mp4": "video",
        ".avi": "video",
        ".mkv": "video",
        ".m2ts": "video",
        ".mov": "video",
        ".ts": "video",
        ".m3u8": "video",
        ".webm": "video",
        ".mpg": "video",
        ".mpeg": "video",
        ".mpeg4": "video",
        ".wmv": "video",
        ".vob": "video",
        ".m4v": "video",
        ".mp3": "audio",
        ".wav": "audio",
        ".flac": "audio",
        ".aac": "audio",
        ".ogg": "audio",
        ".jpg": "photo",
        ".jpeg": "photo",
        ".png": "photo",
        ".bmp": "photo",
        ".gif": "photo",
    }
    _, extension = ospath.splitext(file_path)

    if extension.lower() in extensions_dict:
        return extensions_dict[extension.lower()]
    else:
        return "document"


def shortFileName(path):
    if ospath.isfile(path):
        dir_path, filename = ospath.split(path)
        if len(filename) > 60:
            basename, ext = ospath.splitext(filename)
            basename = basename[: 60 - len(ext)]
            filename = basename + ext
            path = ospath.join(dir_path, filename)
        return path
    elif ospath.isdir(path):
        dir_path, dirname = ospath.split(path)
        if len(dirname) > 60:
            dirname = dirname[:60]
            path = ospath.join(dir_path, dirname)
        return path
    else:
        if len(path) > 60:
            path = path[:60]
        return path


def getSize(path):
    if ospath.isfile(path):
        return ospath.getsize(path)
    else:
        total_size = 0
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                fp = ospath.join(dirpath, f)
                total_size += ospath.getsize(fp)
        return total_size


def videoExtFix(file_path: str):
    _, f_name = ospath.split(file_path)
    if f_name.endswith(".mp4") or f_name.endswith(".mkv"):
        return file_path
    else:
        os.rename(file_path, ospath.join(file_path + ".mp4"))
        return ospath.join(file_path + ".mp4")


def thumbMaintainer(file_path):
    if ospath.exists(Paths.VIDEO_FRAME):
        os.remove(Paths.VIDEO_FRAME)
    try:
        fname, _ = ospath.splitext(ospath.basename(file_path))
        
        # Check for YTDL thumbnail with matching video title (JPG format)
        ytdl_thmb = f"{Paths.WORK_PATH}/ytdl_thumbnails/{fname}.jpg"
        
        # Fallback: Check for any jpg/webp file with similar name pattern
        if not ospath.exists(ytdl_thmb) and ospath.exists(Paths.thumbnail_ytdl):
            for thmb_file in os.listdir(Paths.thumbnail_ytdl):
                if fname in thmb_file and (thmb_file.endswith('.jpg') or thmb_file.endswith('.webp')):
                    ytdl_thmb = ospath.join(Paths.thumbnail_ytdl, thmb_file)
                    break
        
        with VideoFileClip(file_path) as video:
            if ospath.exists(Paths.THMB_PATH):
                return Paths.THMB_PATH, video.duration
            elif ospath.exists(ytdl_thmb):
                # Convert if it's webp, otherwise return as-is
                if ytdl_thmb.endswith('.webp'):
                    return convertIMG(ytdl_thmb), video.duration
                else:
                    return ytdl_thmb, video.duration
            else:
                video.save_frame(Paths.VIDEO_FRAME, t=math.floor(video.duration / 2))
                return Paths.VIDEO_FRAME, video.duration
    except Exception as e:
        print(f"Thmb Gen ERROR: {e}")
        if ospath.exists(Paths.THMB_PATH):
            return Paths.THMB_PATH, 0
        return Paths.HERO_IMAGE, 0


async def setThumbnail(message):
    global SETTING
    try:
        if ospath.exists(Paths.THMB_PATH):
            os.remove(Paths.THMB_PATH)
        event_loop = get_event_loop()
        th_set = event_loop.create_task(message.download(file_name=Paths.THMB_PATH)) 
        await th_set
        BOT.Setting.thumbnail = True
        if BOT.State.task_going and MSG.status_msg:
            await MSG.status_msg.edit_media(
                InputMediaPhoto(Paths.THMB_PATH), reply_markup=keyboard()
            )
        return True
    except Exception as e:
        BOT.Setting.thumbnail = False
        logging.info(f"Error Downloading Thumbnail: {e}")
        return False


def isYtdlComplete():
    for _d, _, filenames in os.walk(Paths.down_path):
        for f in filenames:
            __, ext = ospath.splitext(f)
            if ext in [".part", ".ytdl"]:
                return False
    return True


def convertIMG(image_path):
    image = Image.open(image_path)
    if image.mode != "RGB":
        image = image.convert("RGB")
    output_path = ospath.splitext(image_path)[0] + ".jpg"
    image.save(output_path, "JPEG")
    os.remove(image_path)
    return output_path


def sysINFO():
    ram_usage = psutil.Process(os.getpid()).memory_info().rss
    disk_usage = psutil.disk_usage("/")
    cpu_usage_percent = psutil.cpu_percent()

    string = "\n\n⌬─────「 Colab Usage 」─────⌬\n"
    string += f"\n╭🖥️ **CPU Usage »**  __{cpu_usage_percent}%__"
    string += f"\n├💽 **RAM Usage »**  __{sizeUnit(ram_usage)}__"
    string += f"\n╰💾 **DISK Free »**  __{sizeUnit(disk_usage.free)}__"
    string += Messages.caution_msg

    return string


def multipartArchive(path: str, type: str, remove: bool):
    dirname, filename = ospath.split(path)
    name, _ = ospath.splitext(filename)

    c, size, rname = 1, 0, name
    if type == "rar":
        name_, _ = ospath.splitext(name)
        rname = name_
        na_p = name_ + ".part" + str(c) + ".rar"
        p_ap = ospath.join(dirname, na_p)
        while ospath.exists(p_ap):
            if remove:
                os.remove(p_ap)
            size += getSize(p_ap)
            c += 1
            na_p = name_ + ".part" + str(c) + ".rar"
            p_ap = ospath.join(dirname, na_p)

    elif type == "7z":
        na_p = name + "." + str(c).zfill(3)
        p_ap = ospath.join(dirname, na_p)
        while ospath.exists(p_ap):
            if remove:
                os.remove(p_ap)
            size += getSize(p_ap)
            c += 1
            na_p = name + "." + str(c).zfill(3)
            p_ap = ospath.join(dirname, na_p)

    elif type == "zip":
        na_p = name + ".zip"
        p_ap = ospath.join(dirname, na_p)
        if ospath.exists(p_ap):
            if remove:
                os.remove(p_ap)
            size += getSize(p_ap)
        na_p = name + ".z" + str(c).zfill(2)
        p_ap = ospath.join(dirname, na_p)
        while ospath.exists(p_ap):
            if remove:
                os.remove(p_ap)
            size += getSize(p_ap)
            c += 1
            na_p = name + ".z" + str(c).zfill(2)
            p_ap = ospath.join(dirname, na_p)

        if rname.endswith(".zip"): # When the Archive was file.zip.001
            rname, _ = ospath.splitext(rname)

    return rname, size


def isTimeOver():
    global BotTimes
    ten_sec_passed = time() - BotTimes.current_time >= 3
    if ten_sec_passed:
        BotTimes.current_time = time()
    return ten_sec_passed


def applyCustomName():
    if len(BOT.Options.custom_name) != 0 and BOT.Mode.type not in ["zip", "undzip"]:
        files = os.listdir(Paths.down_path)
        for file_ in files:
            current_name = ospath.join(Paths.down_path, file_)
            new_name = ospath.join(Paths.down_path, BOT.Options.custom_name)
            os.rename(current_name, new_name)


def speedETA(start, done, total):
    percentage = (done / total) * 100
    percentage = 100 if percentage > 100 else percentage
    elapsed_time = (datetime.now() - start).seconds
    if done > 0 and elapsed_time != 0:
        raw_speed = done / elapsed_time
        speed = f"{sizeUnit(raw_speed)}/s"
        eta = (total - done) / raw_speed
    else:
        speed, eta = "N/A", 0
    return speed, eta, percentage


async def message_deleter(message1, message2):
    try:
        await message1.delete()
    except Exception as e:
        logging.error(f"MSG1 Delete Failed: {e}")
    try:
        await message2.delete()
    except Exception as e:
        logging.error(f"MSG2 Delete Failed: {e}")


async def send_settings(client, message, msg_id, command: bool):
    up_mode = "document" if BOT.Options.stream_upload else "media"
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"Set {up_mode.capitalize()}", callback_data=up_mode
                ),
                InlineKeyboardButton("Video Settings", callback_data="video"),
            ],
            [
                InlineKeyboardButton("Caption Font", callback_data="caption"),
                InlineKeyboardButton("Thumbnail", callback_data="thumb"),
            ],
            [
                InlineKeyboardButton("Set Suffix", callback_data="set-suffix"),
                InlineKeyboardButton("Set Prefix", callback_data="set-prefix"),
            ],
            [InlineKeyboardButton("Close ✘", callback_data="close")],
        ]
    )
    text = "**CURRENT BOT SETTINGS ⚙️ »**"
    text += f"\n\n╭⌬ UPLOAD » <i>{BOT.Setting.stream_upload}</i>"
    text += f"\n├⌬ SPLIT » <i>{BOT.Setting.split_video}</i>"
    text += f"\n├⌬ CONVERT » <i>{BOT.Setting.convert_video}</i>"
    text += f"\n├⌬ CAPTION » <i>{BOT.Setting.caption}</i>"
    pr = "None" if BOT.Setting.prefix == "" else "Exists"
    su = "None" if BOT.Setting.suffix == "" else "Exists"
    thmb = "None" if not BOT.Setting.thumbnail else "Exists"
    text += f"\n├⌬ PREFIX » <i>{pr}</i>\n├⌬ SUFFIX » <i>{su}</i>"
    text += f"\n╰⌬ THUMBNAIL » <i>{thmb}</i>"
    try:
        if command:
            await message.reply_text(text=text, reply_markup=keyboard)
        else:
            await colab_bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=msg_id,
                text=text,
                reply_markup=keyboard,
            )
    except BadRequest as error:
        logging.error(f"Same text not modified | {error}")
    except Exception as error:
        logging.error(f"Error Modifying message | {error}")


async def status_bar(down_msg, speed, percentage, eta, done, left, engine):
    bar_length = 12
    filled_length = int(percentage / 100 * bar_length)
    bar = "█" * filled_length + "░" * (bar_length - filled_length)
    text = (
        f"\n╭「{bar}」 **»** __{percentage:.2f}%__\n├⚡️ **Speed »** __{speed}__\n├⚙️ **Engine »** __{engine}__"
        + f"\n├⏳ **Time Left »** __{eta}__"
        + f"\n├🍃 **Time Spent »** __{getTime((datetime.now() - BotTimes.start_time).seconds)}__"
        + f"\n├✅ **Processed »** __{done}__\n╰📦 **Total Size »** __{left}__"
    )
    try:
        # Edit the message with updated progress information.
        if isTimeOver():
            await MSG.status_msg.edit_text(
                text=Messages.task_msg + down_msg + text + sysINFO(),
                disable_web_page_preview=True,
                reply_markup=keyboard(),
            )
    except BadRequest as e:
        logging.error(f"Same Status Not Modified: {str(e)}")
    except Exception as e:
        # Catch any exceptions that might occur while editing the message.
        logging.error(f"Error Updating Status bar: {str(e)}")


def keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Cancel ❌", callback_data="cancel")],
        ]
    )


async def send_auto_delete_photo(client, chat_id, photo_path, caption, delete_after=15, show_close=True):
    """Send a photo with caption that auto-deletes after specified seconds"""
    keyboard = None
    if show_close:
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Close ✘", callback_data="close")]]
        )
    
    try:
        if not ospath.exists(photo_path):
            logging.warning(f"Photo not found: {photo_path}. Sending text only.")
            msg = await client.send_message(
                chat_id=chat_id,
                text=caption,
                reply_markup=keyboard
            )
        else:
            msg = await client.send_photo(
                chat_id=chat_id,
                photo=photo_path,
                caption=caption,
                reply_markup=keyboard
            )
        
        await sleep(delete_after)
        try:
            await msg.delete()
        except Exception as e:
            logging.error(f"Error deleting message: {e}")
    except Exception as e:
        logging.error(f"Error sending photo: {e}")


async def get_speed_test_info():
    """Get Colab download/upload speeds using speedtest library"""
    try:
        import speedtest
        loop = get_event_loop()
        
        def run_speed_test():
            try:
                st = speedtest.Speedtest()
                st.get_best_servers()
                download = st.download() / 1_000_000
                upload = st.upload() / 1_000_000
                return f"📥 Download: {download:.2f} Mbps\n📤 Upload: {upload:.2f} Mbps"
            except Exception as e:
                return f"⚠️ Speed test failed: {str(e)}"
        
        result = await loop.run_in_executor(None, run_speed_test)
        return result
    except ImportError:
        logging.warning("speedtest-cli not installed")
        return "⚠️ Install speedtest-cli: pip install speedtest-cli"


async def get_system_info_detailed():
    """Get detailed Colab system information"""
    try:
        ram_usage = psutil.Process(os.getpid()).memory_info().rss
        disk_usage = psutil.disk_usage("/")
        cpu_usage_percent = psutil.cpu_percent()
        cpu_count = psutil.cpu_count()
        
        info = f"<b>🖥️ SYSTEM INFORMATION</b>\n\n"
        info += f"<b>OS:</b> <code>{platform.system()} {platform.release()}</code>\n"
        info += f"<b>Python:</b> <code>{platform.python_version()}</code>\n\n"
        info += f"<b>📊 RESOURCES:</b>\n"
        info += f"├<b>CPU Usage:</b> <code>{cpu_usage_percent}%</code> (<code>{cpu_count} cores</code>)\n"
        info += f"├<b>RAM Usage:</b> <code>{sizeUnit(ram_usage)}</code>\n"
        info += f"├<b>RAM Total:</b> <code>{sizeUnit(psutil.virtual_memory().total)}</code>\n"
        info += f"├<b>Disk Free:</b> <code>{sizeUnit(disk_usage.free)}</code>\n"
        info += f"╰<b>Disk Total:</b> <code>{sizeUnit(disk_usage.total)}</code>\n\n"
        
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                info += f"<b>🎮 GPU:</b> ✅ <code>{gpu_name}</code>\n"
            else:
                info += f"<b>🎮 GPU:</b> ❌ Not Available\n"
        except ImportError:
            info += f"<b>🎮 GPU:</b> ⚠️ PyTorch not installed\n"
        except Exception as e:
            logging.error(f"GPU detection error: {e}")
            info += f"<b>🎮 GPU:</b> ❌ Error detecting GPU\n"
        
        return info
    except Exception as e:
        logging.error(f"System info error: {e}")
        return f"⚠️ Error: {str(e)}"
