import os
import json
import logging
import asyncio
from flask import Flask, request, jsonify
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, filters, ContextTypes
)
from yt_dlp import YoutubeDL

# ————— Configuración básica —————
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("No BOT_TOKEN environment variable set")

# Opcional: si quieres subir archivos grandes a n8n
N8N_UPLOAD_URL = os.getenv("N8N_UPLOAD_URL", None)

# Límites y constantes
TELEGRAM_FILE_LIMIT = 50 * 1024 * 1024  # 50 MB
ELEGIR_TIPO = range(1)

# ————— Inicializa el bot de Telegram —————
application = Application.builder().token(BOT_TOKEN).build()

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Envía el enlace del vídeo que quieres descargar "
        "(YouTube, TikTok, Instagram, etc.)"
    )
application.add_handler(CommandHandler("start", start))

# Función helper: detecta plataforma
def detectar_plataforma(url: str) -> str:
    plataformas = {
        'youtube.com': 'YouTube 📺', 'youtu.be': 'YouTube 📺',
        'instagram.com': 'Instagram 📸',
        'tiktok.com': 'TikTok 🎵',
        'twitter.com': 'Twitter 🐦', 'x.com': 'Twitter 🐦',
        'facebook.com': 'Facebook 👍', 'fb.watch': 'Facebook 👍',
        'vimeo.com': 'Vimeo 🎞️', 'dailymotion.com': 'Dailymotion 📹',
        'reddit.com': 'Reddit 👽'
    }
    for key, nombre in plataformas.items():
        if key in url:
            return nombre
    return 'desconocida ❓'

# Paso 1 Telegram: recibimos URL
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

# Paso 2 Telegram: elegimos tipo
async def elegir_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    eleccion = update.message.text.strip().lower()
    url = context.user_data['url']
    download_type = 'audio' if 'audio' in eleccion else 'video'

    # Llamamos internamente a nuestra ruta /download
    download_endpoint = f"{request.url_root}api/download"
    resp = requests.post(download_endpoint, json={'url': url, 'type': download_type})
    data = resp.json()

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
        # si excede límite y tenemos N8N_UPLOAD_URL
        if N8N_UPLOAD_URL:
            with open(file_path, 'rb') as f:
                files = {'file': (filename, f)}
                up = requests.post(N8N_UPLOAD_URL, files=files)
            if up.ok and up.json().get('download_url'):
                await update.message.reply_text(
                    f"✅ Muy grande para Telegram.\n"
                    f"Descárgalo aquí: {up.json()['download_url']}"
                )
                return ConversationHandler.END

        await update.message.reply_text("❌ El archivo es demasiado grande.")
    return ConversationHandler.END

# Cancelar
async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operación cancelada.")
    return ConversationHandler.END

conv = ConversationHandler(
    entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_url)],
    states={ELEGIR_TIPO: [MessageHandler(filters.TEXT, elegir_tipo)]},
    fallbacks=[CommandHandler('cancelar', cancelar)]
)
application.add_handler(conv)

# ————— Rutas HTTP —————

@app.route("/api/webhook", methods=["POST"])
def webhook():
    """Endpoint para Telegram (webhook)."""
    update = Update.de_json(request.get_json(force=True), application.bot)
    # Procesa el update
    asyncio.run(application.initialize())
    asyncio.run(application.process_update(update))
    return jsonify({"ok": True})

@app.route("/api/download", methods=["POST"])
def download_route():
    """Endpoint para n8n o llamadas directas."""
    data = request.get_json(force=True)
    url = data.get('url')
    d_type = data.get('type', 'video')

    # Configuración de yt-dlp
    quality = 'bestaudio/best' if d_type=='audio' else 'bestvideo+bestaudio'
    if 'tiktok.com' in url and d_type=='video':
        quality = 'best'

    opts = {
        'format': quality,
        'noplaylist': True,
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'windowsfilenames': True,
    }
    if d_type == 'audio':
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        opts['merge_output_format'] = 'mp4'

    os.makedirs('downloads', exist_ok=True)
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info)
            if d_type=='audio':
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
        logging.exception("Error download")
        return jsonify(status='error', message=str(e)), 500

# ————— Ejecuta en Render con gunicorn —————
# En tu dashboard de Render pon:
# Start Command: gunicorn app:app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
