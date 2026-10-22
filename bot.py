import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
import requests
import io
import os
import subprocess
import uuid
import json
import html
import yt_dlp
from bs4 import BeautifulSoup

# Mengambil token dari GitHub Secrets (Environment Variables)
TG_TOKEN = os.getenv("TG_TOKEN", "8821734542:AAE0CqFeawlkXSYlSkfHfGxcfTERdepN1so")
ADMIN_ID = os.getenv("ADMIN_ID", "7958950292")

bot = telebot.TeleBot(TG_TOKEN, threaded=True)
music_cache = {}

def is_admin(message):
    return str(message.chat.id) == str(ADMIN_ID)

def format_size(bytes_size):
    return f"{bytes_size / (1024 * 1024):.2f} MB"

# ==========================================
# 0. MENU START & HELP
# ==========================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if not is_admin(message): return
    menu_text = (
        "🤖 <b>ULTIMATE AI & MEDIA BOT v3.0</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "✨ <b>AI Real-ESRGAN Photo Upscaler</b>\n"
        "• Kirim foto atau dokumen gambar untuk di-upscale dengan AI Real-ESRGAN agar super tajam.\n\n"
        "🎬 <b>HD Video Upscaler (1080p)</b>\n"
        "• Kirim video (maks 20MB) untuk di-render ke Full HD 1080p (Lanczos + Unsharp).\n\n"
        "📥 <b>All-in-One Downloader (No WM)</b>\n"
        "• <b>TikTok:</b> Video HD, Slide Foto, & Audio MP3\n"
        "• <b>Instagram:</b> Reels & Post Video\n"
        "• <b>YouTube:</b> YouTube Shorts & Video pendek\n\n"
        "🕵️‍♂️ <b>TikTok OSINT</b>\n"
        "• Ketik <code>/tt username</code> untuk lacak profil lengkap & unduh avatar HD."
    )
    bot.reply_to(message, menu_text, parse_mode='HTML')

# ==========================================
# 1. AI REAL-ESRGAN PHOTO UPSCALER
# ==========================================
def process_image_upscale(message, file_id):
    msg = bot.reply_to(message, "⏳ <i>Memproses gambar dengan AI Real-ESRGAN...</i>", parse_mode='HTML')
    uid = uuid.uuid4().hex
    in_img = f"in_{uid}.jpg"
    out_img = f"HD_RealESRGAN_{uid}.png"

    try:
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        with open(in_img, 'wb') as f:
            f.write(downloaded_file)

        engine_used = "AI Real-ESRGAN"

        # Cek apakah binary Real-ESRGAN tersedia (diinstal otomatis di GitHub Actions)
        if os.path.exists("./realesrgan-ncnn-vulkan"):
            # Menggunakan model realesr-animevideov3-x2 (cepat di CPU Vulkan & tajam untuk foto/ilustrasi)
            # Bisa diganti ke 'realesrgan-x4plus' jika ingin upscale 4x lipat
            cmd = [
                "./realesrgan-ncnn-vulkan",
                "-i", in_img,
                "-o", out_img,
                "-n", "realesr-animevideov3-x2",
                "-s", "2",
                "-f", "png"
            ]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if proc.returncode != 0 or not os.path.exists(out_img):
                raise Exception("Gagal menjalankan binary Real-ESRGAN, beralih ke fallback.")
        else:
            # Fallback otomatis ke FFmpeg Lanczos + CAS jika dijalankan tanpa Real-ESRGAN
            engine_used = "FFmpeg Lanczos + Smart Sharpen"
            cmd = [
                "ffmpeg", "-i", in_img,
                "-vf", "scale=iw*2:ih*2:flags=lanczos,unsharp=5:5:1.0:3:3:0.5",
                out_img, "-y"
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

        bot.edit_message_text("⏳ <i>Mengunggah hasil HD tanpa kompresi...</i>", chat_id=message.chat.id, message_id=msg.message_id, parse_mode='HTML')
        with open(out_img, 'rb') as f_out:
            bot.send_document(
                message.chat.id, f_out,
                caption=f"✅ <b>Berhasil di-Upscale!</b>\n🧠 <b>Engine:</b> <code>{engine_used}</code>\n📏 <b>Resolusi:</b> 2x Lipat Lossless PNG",
                parse_mode='HTML', reply_to_message_id=message.message_id
            )
        bot.delete_message(message.chat.id, msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"❌ <b>Error Upscale:</b> <code>{html.escape(str(e))}</code>", chat_id=message.chat.id, message_id=msg.message_id, parse_mode='HTML')
    finally:
        if os.path.exists(in_img): os.remove(in_img)
        if os.path.exists(out_img): os.remove(out_img)

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    if not is_admin(message): return
    process_image_upscale(message, message.photo[-1].file_id)

# ==========================================
# 2. HD VIDEO UPSCALER (FFMPEG 1080P)
# ==========================================
@bot.message_handler(content_types=['video', 'document'])
def handle_video_or_doc(message):
    if not is_admin(message): return

    if message.document:
        mime = message.document.mime_type or ""
        if mime.startswith("image/"):
            return process_image_upscale(message, message.document.file_id)
        elif not mime.startswith("video/"):
            return bot.reply_to(message, "⚠️ <b>Format tidak didukung!</b> Kirim file berupa Foto atau Video.", parse_mode='HTML')

    media = message.video if message.video else message.document
    if media.file_size > 20 * 1024 * 1024:
        return bot.reply_to(message, f"❌ <b>Video terlalu besar ({format_size(media.file_size)})!</b> Maksimal 20 MB.", parse_mode='HTML')

    msg = bot.reply_to(message, "⏳ <i>Mengunduh & merender video ke 1080p...</i>", parse_mode='HTML')
    input_name = f"in_{uuid.uuid4().hex}.mp4"
    output_name = f"out_{uuid.uuid4().hex}.mp4"

    try:
        file_info = bot.get_file(media.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        with open(input_name, 'wb') as f:
            f.write(downloaded_file)

        vf_filter = "scale='if(gt(iw,ih),1920,-2)':'if(gt(iw,ih),-2,1920)':flags=lanczos,unsharp=5:5:0.6:3:3:0.3"
        cmd = [
            "ffmpeg", "-i", input_name,
            "-vf", vf_filter,
            "-c:v", "libx264", "-crf", "21", "-preset", "faster",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            output_name, "-y"
        ]
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if process.returncode != 0:
            raise Exception("Gagal merender video dengan FFmpeg.")

        out_size = os.path.getsize(output_name)
        if out_size > 50 * 1024 * 1024:
            bot.edit_message_text(f"❌ <b>Hasil video terlalu besar ({format_size(out_size)})!</b> Batas Telegram 50 MB.", chat_id=message.chat.id, message_id=msg.message_id, parse_mode='HTML')
        else:
            with open(output_name, 'rb') as vid:
                bot.send_video(
                    message.chat.id, vid,
                    caption=f"✅ <b>Video Berhasil di-Upscale ke 1080p!</b>\n📦 Ukuran: <code>{format_size(out_size)}</code>",
                    parse_mode='HTML', supports_streaming=True, reply_to_message_id=message.message_id
                )
            bot.delete_message(message.chat.id, msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ <b>Error:</b> <code>{html.escape(str(e))}</code>", chat_id=message.chat.id, message_id=msg.message_id, parse_mode='HTML')
    finally:
        if os.path.exists(input_name): os.remove(input_name)
        if os.path.exists(output_name): os.remove(output_name)

# ==========================================
# 3. TIKTOK OSINT COMMAND (/tt)
# ==========================================
@bot.message_handler(commands=['tt'])
def handle_tiktok_osint(message):
    if not is_admin(message): return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return bot.reply_to(message, "⚠️ Gunakan format: <code>/tt username</code>", parse_mode='HTML')

    target = parts[1].strip().replace('@', '')
    msg = bot.reply_to(message, f"⏳ <i>Melacak OSINT TikTok <code>@{html.escape(target)}</code>...</i>", parse_mode='HTML')

    user_data, stats_data = None, None
    try:
        res = requests.get(f"https://tikwm.com/api/user/info?unique_id={target}", timeout=12).json()
        if res.get('code') == 0 and res.get('data'):
            user_data = res['data'].get('user', {})
            stats_data = res['data'].get('stats', {})
    except Exception:
        pass

    if not user_data:
        try:
            r = requests.get(f"https://www.tiktok.com/@{target}", headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            script = soup.find('script', id='__UNIVERSAL_DATA_FOR_REHYDRATION__')
            if script:
                data = json.loads(script.string)
                u_info = data['__DEFAULT_SCOPE__']['webapp.user-detail']['userInfo']
                user_data, stats_data = u_info.get('user', {}), u_info.get('stats', {})
        except Exception:
            pass

    if not user_data:
        return bot.edit_message_text("❌ <b>User tidak ditemukan.</b>", chat_id=message.chat.id, message_id=msg.message_id, parse_mode='HTML')

    nickname = html.escape(user_data.get('nickname', '-'))
    unique_id = html.escape(user_data.get('uniqueId', target))
    user_id = html.escape(str(user_data.get('id', '-')))
    bio = html.escape(user_data.get('signature', '') or '-')
    avatar_url = user_data.get('avatarLarger') or user_data.get('avatarMedium')
    is_private = "🔒 Privat" if user_data.get('privateAccount') else "🌐 Publik"

    report = (
        f"🕵️‍♂️ <b>TIKTOK OSINT REPORT</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Nama:</b> {nickname}\n"
        f"🔖 <b>Username:</b> <code>@{unique_id}</code>\n"
        f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
        f"🛡️ <b>Status:</b> {is_private}\n"
        f"📝 <b>Bio:</b> <i>{bio}</i>\n\n"
        f"📊 <b>Followers:</b> {stats_data.get('followerCount', 0):,}\n"
        f"❤️ <b>Total Likes:</b> {stats_data.get('heartCount', 0):,}\n"
        f"🎬 <b>Total Video:</b> {stats_data.get('videoCount', 0):,}"
    )

    try:
        if avatar_url:
            bot.send_photo(message.chat.id, avatar_url, caption=report, parse_mode='HTML', reply_to_message_id=message.message_id)
            bot.delete_message(message.chat.id, msg.message_id)
        else:
            bot.edit_message_text(report, chat_id=message.chat.id, message_id=msg.message_id, parse_mode='HTML')
    except Exception:
        bot.edit_message_text(report, chat_id=message.chat.id, message_id=msg.message_id, parse_mode='HTML')

# ==========================================
# 4. IG REELS, YT SHORTS & TIKTOK DOWNLOADER
# ==========================================
def download_with_ytdlp(message, url, platform_name):
    msg = bot.reply_to(message, f"⏳ <i>Mengunduh video {platform_name}...</i>", parse_mode='HTML')
    out_tmpl = f"dl_{uuid.uuid4().hex}.%(ext)s"
    final_file = None

    ydl_opts = {
        'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': out_tmpl,
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'max_filesize': 49 * 1024 * 1024,
        'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            final_file = ydl.prepare_filename(info)
            if not os.path.exists(final_file):
                base = os.path.splitext(final_file)[0]
                if os.path.exists(base + ".mp4"):
                    final_file = base + ".mp4"

            title = html.escape((info.get('title') or f'{platform_name} Video')[:180])
            uploader = html.escape(info.get('uploader') or info.get('channel') or 'Unknown')

        bot.edit_message_text("⏳ <i>Mengunggah video ke Telegram...</i>", chat_id=message.chat.id, message_id=msg.message_id, parse_mode='HTML')
        with open(final_file, 'rb') as v:
            bot.send_video(
                message.chat.id, v,
                caption=f"✅ <b>{title}</b>\n👤 <b>Channel/Creator:</b> <code>{uploader}</code>\n🌐 <b>Sumber:</b> {platform_name}",
                parse_mode='HTML', supports_streaming=True, reply_to_message_id=message.message_id
            )
        bot.delete_message(message.chat.id, msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ <b>Gagal mengunduh {platform_name}:</b>\n<code>{html.escape(str(e)[:200])}</code>", chat_id=message.chat.id, message_id=msg.message_id, parse_mode='HTML')
    finally:
        if final_file and os.path.exists(final_file):
            os.remove(final_file)

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    if not is_admin(message) or not message.text: return
    text = message.text.strip()

    # Handler Instagram Reels / Post
    if "instagram.com/" in text:
        return download_with_ytdlp(message, text, "Instagram Reels")

    # Handler YouTube Shorts / Video
    if any(k in text for k in ["youtube.com/shorts/", "youtu.be/", "youtube.com/watch"]):
        return download_with_ytdlp(message, text, "YouTube Shorts")

    # Handler TikTok (Video HD, Slide Foto & MP3)
    if "tiktok.com" in text:
        msg = bot.reply_to(message, "⏳ <i>Mengekstrak media TikTok...</i>", parse_mode='HTML')
        try:
            res = requests.get("https://tikwm.com/api/", params={'url': text, 'hd': 1}, timeout=15).json()
            if res.get('code') != 0 or not res.get('data'):
                return bot.edit_message_text("❌ <b>Gagal mengambil data TikTok!</b>", chat_id=message.chat.id, message_id=msg.message_id, parse_mode='HTML')

            data = res['data']
            title = html.escape(data.get('title', 'TikTok Media')[:200])
            author = html.escape(data.get('author', {}).get('unique_id', 'unknown'))
            music_url = data.get('music')

            caption = f"✅ <b>{title}</b>\n👤 <b>Creator:</b> <code>@{author}</code>"

            markup = None
            if music_url:
                short_id = uuid.uuid4().hex[:8]
                music_cache[short_id] = {'url': music_url, 'title': data.get('music_info', {}).get('title', 'TikTok_Audio')}
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("🎵 Unduh Audio (MP3)", callback_data=f"mp3_{short_id}"))

            images = data.get('images')
            if images:
                media_group = [InputMediaPhoto(img, caption=caption if i == 0 else None, parse_mode='HTML') for i, img in enumerate(images[:10])]
                bot.send_media_group(message.chat.id, media_group, reply_to_message_id=message.message_id)
                if markup:
                    bot.send_message(message.chat.id, "👇 <b>Unduh musik latar slide:</b>", parse_mode='HTML', reply_markup=markup)
                bot.delete_message(message.chat.id, msg.message_id)
                return

            video_url = data.get('hdplay') or data.get('play')
            try:
                bot.send_video(message.chat.id, video_url, caption=caption, parse_mode='HTML', reply_markup=markup, reply_to_message_id=message.message_id)
            except Exception:
                bot.send_video(message.chat.id, data.get('play'), caption=caption, parse_mode='HTML', reply_markup=markup, reply_to_message_id=message.message_id)
            bot.delete_message(message.chat.id, msg.message_id)
        except Exception as e:
            bot.edit_message_text(f"❌ <b>Error:</b> <code>{html.escape(str(e))}</code>", chat_id=message.chat.id, message_id=msg.message_id, parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data.startswith('mp3_'))
def handle_mp3_callback(call):
    short_id = call.data.split('_')[1]
    info = music_cache.get(short_id)
    if not info:
        return bot.answer_callback_query(call.id, "❌ Sesi audio kedaluwarsa.", show_alert=True)

    bot.answer_callback_query(call.id, "⏳ Mengirim MP3...")
    try:
        audio_res = requests.get(info['url'], timeout=15)
        audio_io = io.BytesIO(audio_res.content)
        audio_io.name = f"{info['title'][:30]}.mp3"
        bot.send_audio(call.message.chat.id, audio_io, title=info['title'], caption="🎵 <b>TikTok Audio</b>", parse_mode='HTML')
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Error MP3: <code>{html.escape(str(e))}</code>", parse_mode='HTML')

if __name__ == "__main__":
    print("[*] Bot v3.0 Running...")
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
