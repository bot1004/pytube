import os
import json
import logging
import asyncio
import random
import threading
import time
from flask import Flask, request, jsonify
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, filters, ContextTypes
)
from yt_dlp import YoutubeDL
import requests
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ————— Configuración —————
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
if not BOT_TOKEN:
    raise ValueError("No BOT_TOKEN environment variable set")
if not YOUTUBE_API_KEY:
    raise ValueError("No YOUTUBE_API_KEY environment variable set")

N8N_UPLOAD_URL = os.getenv("N8N_UPLOAD_URL", None)
TELEGRAM_FILE_LIMIT = 50 * 1024 * 1024
ELEGIR_TIPO = range(1)

# Lista de proxies gratuitos con puntuación
PROXY_LIST = {
    'http://103.149.162.195:80': {'score': 0, 'last_check': 0},
    'http://103.152.232.194:8080': {'score': 0, 'last_check': 0},
    'http://103.152.232.230:8080': {'score': 0, 'last_check': 0},
    'http://103.152.232.234:8080': {'score': 0, 'last_check': 0},
    'http://103.152.232.235:8080': {'score': 0, 'last_check': 0},
    'http://103.152.232.236:8080': {'score': 0, 'last_check': 0},
    'http://103.152.232.237:8080': {'score': 0, 'last_check': 0},
    'http://103.152.232.238:8080': {'score': 0, 'last_check': 0},
    'http://103.152.232.239:8080': {'score': 0, 'last_check': 0},
    'http://103.152.232.240:8080': {'score': 0, 'last_check': 0}
}

# Nuevos proxies para añadir cuando sea necesario
NEW_PROXIES = [
    'http://103.149.162.196:80',
    'http://103.152.232.241:8080',
    'http://103.152.232.242:8080',
    'http://103.152.232.243:8080',
    'http://103.152.232.244:8080'
]

def check_proxy(proxy):
    try:
        start_time = time.time()
        response = requests.get(
            'https://www.google.com',
            proxies={'http': proxy, 'https': proxy},
            timeout=5
        )
        if response.status_code == 200:
            response_time = time.time() - start_time
            return True, response_time
        return False, None
    except:
        return False, None

def update_proxy_scores():
    while True:
        try:
            for proxy in list(PROXY_LIST.keys()):
                is_working, response_time = check_proxy(proxy)
                current_time = time.time()
                
                if is_working:
                    # Aumentar puntuación si funciona
                    PROXY_LIST[proxy]['score'] = min(PROXY_LIST[proxy]['score'] + 1, 10)
                    if response_time:
                        # Ajustar puntuación basada en velocidad
                        speed_bonus = max(0, 1 - (response_time / 5))
                        PROXY_LIST[proxy]['score'] = min(PROXY_LIST[proxy]['score'] + speed_bonus, 10)
                else:
                    # Reducir puntuación si falla
                    PROXY_LIST[proxy]['score'] = max(0, PROXY_LIST[proxy]['score'] - 2)
                
                PROXY_LIST[proxy]['last_check'] = current_time
                
                # Eliminar proxies con puntuación 0
                if PROXY_LIST[proxy]['score'] == 0:
                    del PROXY_LIST[proxy]
                    # Añadir nuevo proxy si hay disponibles
                    if NEW_PROXIES:
                        new_proxy = NEW_PROXIES.pop(0)
                        PROXY_LIST[new_proxy] = {'score': 0, 'last_check': current_time}
            
            # Ordenar proxies por puntuación
            sorted_proxies = sorted(PROXY_LIST.items(), key=lambda x: x[1]['score'], reverse=True)
            logging.info(f"Proxies actualizados. Mejores proxies: {[p[0] for p in sorted_proxies[:3]]}")
            
            # Esperar 5 minutos antes de la siguiente verificación
            time.sleep(300)
        except Exception as e:
            logging.error(f"Error en la actualización de proxies: {str(e)}")
            time.sleep(60)

def get_best_proxy():
    if not PROXY_LIST:
        return None
    # Obtener el proxy con mayor puntuación
    return max(PROXY_LIST.items(), key=lambda x: x[1]['score'])[0]

def get_random_proxy():
    if not PROXY_LIST:
        return None
    # Obtener un proxy aleatorio de los que tienen puntuación > 0
    working_proxies = [p for p, data in PROXY_LIST.items() if data['score'] > 0]
    return random.choice(working_proxies) if working_proxies else None

# Iniciar el thread de verificación de proxies
proxy_checker_thread = threading.Thread(target=update_proxy_scores, daemon=True)
proxy_checker_thread.start()

def get_ydl_opts(d_type, url):
    proxy = get_best_proxy()  # Usar el mejor proxy disponible
    if not proxy:
        logging.warning("No hay proxies disponibles")
        proxy = None

    quality = 'bestaudio/best' if d_type == 'audio' else 'bestvideo+bestaudio'
    if 'tiktok.com' in url.lower() and d_type == 'video':
        quality = 'best'

    opts = {
        'format': quality,
        'noplaylist': True,
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'windowsfilenames': True,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'ignoreerrors': True,
        'no_check_certificate': True,
        'prefer_insecure': True,
        'geo_bypass': True,
        'geo_verification_proxy': None,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Sec-Fetch-Mode': 'navigate',
            'DNT': '1',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Connection': 'keep-alive',
        },
        'socket_timeout': 30,
        'retries': 10,
        'fragment_retries': 10,
        'skip_download_archive': True,
        'extractor_retries': 3,
        'ignoreerrors': True,
        'no_warnings': True,
        'quiet': True,
        'no_color': True,
        'prefer_ffmpeg': True,
        'postprocessor_args': [
            '-threads', '0',
            '-preset', 'ultrafast',
            '-tune', 'fastdecode',
        ],
    }

    if proxy:
        opts['proxy'] = proxy

    if d_type == 'audio':
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        opts['merge_output_format'] = 'mp4'

    return opts

application = Application.builder().token(BOT_TOKEN).build()

def get_youtube_service():
    return build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

def is_youtube_url(url):
    return 'youtube.com' in url or 'youtu.be' in url

def get_video_id(url):
    if 'youtube.com/watch?v=' in url:
        return url.split('watch?v=')[1].split('&')[0]
    elif 'youtu.be/' in url:
        return url.split('youtu.be/')[1].split('?')[0]
    return None

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ El bot está funcionando desde Render! 🚀\nEnvía el enlace del vídeo que quieres descargar."
    )

application.add_handler(CommandHandler("start", start))

def detectar_plataforma(url: str) -> str:
    plataformas = {
        'youtube.com': 'YouTube 📺', 'youtu.be': 'YouTube 📺',
        'instagram.com': 'Instagram 📸', 'tiktok.com': 'TikTok 🎵',
        'twitter.com': 'Twitter 🐦', 'x.com': 'Twitter 🐦',
        'facebook.com': 'Facebook 👍', 'fb.watch': 'Facebook 👍',
        'vimeo.com': 'Vimeo 🎞️', 'dailymotion.com': 'Dailymotion 📹',
        'reddit.com': 'Reddit 👽'
    }
    for key, nombre in plataformas.items():
        if key in url:
            return nombre
    return 'desconocida ❓'

async def recibir_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    context.user_data['url'] = url
    plataforma = detectar_plataforma(url)

    keyboard = [["🎬 Vídeo completo", "🎵 Solo audio"]]
    await update.message.reply_text(
        f"He detectado {plataforma}.\n¿Qué deseas descargar?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return ELEGIR_TIPO

async def elegir_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    eleccion = update.message.text.strip().lower()
    url = context.user_data['url']
    download_type = 'audio' if 'audio' in eleccion else 'video'

    try:
        resp = requests.post(request.url_root + "api/download", json={'url': url, 'type': download_type})
        data = resp.json()
    except Exception as e:
        await update.message.reply_text("❌ Error al contactar con la API.")
        return ConversationHandler.END

    if data.get('status') != 'success':
        await update.message.reply_text(f"❌ Error: {data.get('message')}")
        return ConversationHandler.END

    filename = data['filename']
    file_path = os.path.join("downloads", filename)
    size = os.path.getsize(file_path)

    if size <= TELEGRAM_FILE_LIMIT:
        await update.message.reply_document(
            document=open(file_path, 'rb'),
            caption=(
                f"✅ Archivo descargado:\n"
                f"📹 {data['metadata']['title']}\n"
                f"👤 {data['metadata']['author']}\n"
                f"⏱ {data['metadata']['length']} s"
            )
        )
    else:
        if N8N_UPLOAD_URL:
            with open(file_path, 'rb') as f:
                files = {'file': (filename, f)}
                up = requests.post(N8N_UPLOAD_URL, files=files)
            if up.ok and up.json().get('download_url'):
                await update.message.reply_text(
                    f"✅ Muy grande para Telegram.\n"
                    f"Descárgalo aquí: {up.json()['download_url']}"
                )
            else:
                await update.message.reply_text("❌ Error al subir el archivo a n8n.")
        else:
            await update.message.reply_text("❌ El archivo es demasiado grande.")
    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operación cancelada.")
    return ConversationHandler.END

conv = ConversationHandler(
    entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_url)],
    states={ELEGIR_TIPO: [MessageHandler(filters.TEXT, elegir_tipo)]},
    fallbacks=[CommandHandler('cancelar', cancelar)]
)
application.add_handler(conv)

# Ruta principal (home)
@app.route("/", methods=["GET"])
def home():
    return "✅ El bot y la API están funcionando en Render."

# Webhook Telegram
@app.route("/api/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.run(application.initialize())
    asyncio.run(application.process_update(update))
    return jsonify({"ok": True})

# API de descarga
@app.route("/api/download", methods=["POST"])
def download_route():
    data = request.get_json(force=True)
    url = data.get('url')
    d_type = data.get('type', 'video')

    os.makedirs('downloads', exist_ok=True)
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            opts = get_ydl_opts(d_type, url)
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                path = ydl.prepare_filename(info)
                if d_type == 'audio':
                    path = os.path.splitext(path)[0] + ".mp3"

            fname = os.path.basename(path)
            meta = {
                'title': info.get('title'),
                'author': info.get('uploader'),
                'length': info.get('duration'),
                'type': d_type
            }
            return jsonify(status='success', filename=fname, metadata=meta)

        except Exception as e:
            retry_count += 1
            logging.warning(f"Intento {retry_count} fallido: {str(e)}")
            if retry_count == max_retries:
                logging.exception("Error download después de todos los intentos")
                return jsonify(status='error', message=str(e)), 500
            continue

    return jsonify(status='error', message="Error después de varios intentos"), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
