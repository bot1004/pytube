import os
import json
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Configura el log por si hay errores
logging.basicConfig(level=logging.INFO)

# Lee el token del bot desde variable de entorno
BOT_TOKEN = os.environ["8121623575:AAH798Us_OvXfiejYhURKDfxA3m4yXWe3PM"]

# Crea la aplicación del bot de Telegram
application = Application.builder().token(BOT_TOKEN).build()

# Comando de inicio básico
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ El bot está funcionando desde Netlify! 🚀\nEnvía un enlace para comenzar.")

# Añade el comando /start al bot
application.add_handler(CommandHandler("start", start))

# Esta es la función que Netlify ejecutará (entrada principal del webhook)
def handler(event, context):
    try:
        # Parsear el body del request (update que Telegram manda)
        body = json.loads(event["body"])

        # Convertir el update a formato de Telegram
        update = Update.de_json(body, application.bot)

        # Procesarlo en el event loop de asyncio
        loop = asyncio.get_event_loop()
        loop.run_until_complete(application.initialize())
        loop.run_until_complete(application.process_update(update))

        return {
            "statusCode": 200,
            "body": json.dumps({"status": "ok"})
        }

    except Exception as e:
        logging.exception("❌ Error en el webhook")
        return {
            "statusCode": 500,
            "body": json.dumps({"status": "error", "message": str(e)})
        }
