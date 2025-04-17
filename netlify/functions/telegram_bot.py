import os
import json
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import logging
from pathlib import Path

from telegram.ext.webhook import WebhookServer

ELEGIR_TIPO = range(1)
TELEGRAM_FILE_LIMIT = 50 * 1024 * 1024

BOT_TOKEN = os.environ["8121623575:AAH798Us_OvXfiejYhURKDfxA3m4yXWe3PM"]

application = Application.builder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Envíame el link del video")

async def recibir_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    context.user_data['url'] = url
    await update.message.reply_text("¿Quieres video o solo audio?")
    return ELEGIR_TIPO

async def elegir_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tipo = update.message.text.lower()
    url = context.user_data['url']
    download_type = 'audio' if 'audio' in tipo else 'video'

    # Llamamos a la función Netlify (autollamada)
    api_url = os.environ['DOWNLOAD_API_URL']
    response = requests.post(api_url, json={'url': url, 'type': download_type})
    data = response.json()

    if data['status'] != 'success':
        await update.message.reply_text("❌ Error: " + data['message'])
        return ConversationHandler.END

    filename = data['filename']
    filepath = Path('downloads') / filename

    if filepath.stat().st_size <= TELEGRAM_FILE_LIMIT:
        await update.message.reply_document(document=open(filepath, 'rb'))
    else:
        await update.message.reply_text("El archivo es muy grande. Descárgalo desde: (aquí pondríamos un link a otra función si quieres)")

    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelado.")
    return ConversationHandler.END

conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_url)],
    states={ELEGIR_TIPO: [MessageHandler(filters.TEXT, elegir_tipo)]},
    fallbacks=[CommandHandler("cancelar", cancelar)]
)

application.add_handler(CommandHandler("start", start))
application.add_handler(conv_handler)

def handler(event, context):
    return {
        "statusCode": 200,
        "body": "Bot funcionando desde Netlify"
    }
