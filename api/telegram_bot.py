import os
import json
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Configura el token desde variable de entorno
BOT_TOKEN = os.environ["8121623575:AAH798Us_OvXfiejYhURKDfxA3m4yXWe3PM"]

# Inicializa la app de Telegram
application = Application.builder().token(BOT_TOKEN).build()

# /start responderá con este mensaje
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ El bot está funcionando desde Vercel! 🚀\nEnvía un enlace para comenzar.")

# Añade el comando al bot
application.add_handler(CommandHandler("start", start))

# Vercel llama a esta función en cada petición
async def handler(request):
    try:
        body = await request.json()
        update = Update.de_json(body, application.bot)

        await application.initialize()
        await application.process_update(update)

        return {
            "statusCode": 200,
            "body": json.dumps({"status": "ok"})
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"status": "error", "message": str(e)})
        }
