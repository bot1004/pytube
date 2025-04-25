import os
import uuid
import logging
import subprocess
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from celery import Celery
import yt_dlp
import pytube
import instaloader
import time
import ffmpeg
import random

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializar Flask
app = Flask(__name__)
CORS(app)

# Configuración de Celery con variables de entorno para Render.com
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# Asegurarse de que la URL comienza con 'redis://'
if not redis_url.startswith('redis://') and not redis_url.startswith('rediss://'):
    redis_url = 'redis://' + redis_url

logger.info(f"Usando Redis URL: {redis_url}")

# Configuración de Celery
app.config['broker_url'] = redis_url
app.config['result_backend'] = redis_url

# Crear directorio para descargas si no existe
DOWNLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)
    logger.info(f"Directorio de descargas creado: {DOWNLOAD_FOLDER}")

# Inicializar Celery
celery = Celery(
    app.name,
    broker=app.config['broker_url'],
    backend=app.config['result_backend']
)
celery.conf.update(app.config)

# Almacenamiento temporal de estado de tareas
task_status = {}

def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def get_random_user_agent():
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15'
    ]
    return random.choice(user_agents)

@celery.task(bind=True, max_retries=3)
def download_task(self, url, media_type, quality=None):
    task_id = self.request.id
    logger.info(f"Tarea {task_id}: Iniciando descarga de {url}")
    task_status[task_id] = {"status": "processing", "message": "Iniciando descarga..."}
    
    try:
        # Verificar ffmpeg
        if not check_ffmpeg():
            raise Exception("ffmpeg no está instalado. Por favor, instálalo para continuar.")
        
        filename = None
        download_path = None
        
        # Generar un nombre de archivo único
        unique_filename = f"{uuid.uuid4().hex}"
        logger.info(f"Tarea {task_id}: Nombre de archivo único generado: {unique_filename}")
        
        if 'youtube.com' in url or 'youtu.be' in url:
            logger.info(f"Tarea {task_id}: Detectada URL de YouTube")
            
            try:
                # Configurar pytube con headers personalizados
                yt = pytube.YouTube(
                    url,
                    use_oauth=False,
                    allow_oauth_cache=False,
                    http_client=None,
                    http_headers={
                        'User-Agent': get_random_user_agent(),
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-us,en;q=0.5',
                        'Sec-Fetch-Mode': 'navigate',
                        'DNT': '1',
                        'Upgrade-Insecure-Requests': '1',
                        'Cache-Control': 'max-age=0',
                        'Connection': 'keep-alive',
                    }
                )
                
                if media_type == 'audio':
                    logger.info(f"Tarea {task_id}: Configurando descarga de audio")
                    stream = yt.streams.filter(only_audio=True).first()
                    if not stream:
                        raise Exception("No se encontró stream de audio")
                        
                    # Descargar el archivo
                    download_path = stream.download(output_path=DOWNLOAD_FOLDER, filename=f"{unique_filename}.mp4")
                    
                    # Convertir a MP3 usando ffmpeg
                    mp3_path = os.path.join(DOWNLOAD_FOLDER, f"{unique_filename}.mp3")
                    try:
                        stream = ffmpeg.input(download_path)
                        stream = ffmpeg.output(stream, mp3_path, acodec='libmp3lame', q=2)
                        ffmpeg.run(stream, capture_stdout=True, capture_stderr=True)
                    except ffmpeg.Error as e:
                        logger.error(f"Error en ffmpeg: {e.stderr.decode()}")
                        raise Exception("Error al convertir el audio a MP3")
                    
                    # Eliminar el archivo original
                    os.remove(download_path)
                    download_path = mp3_path
                    
                else:  # video
                    logger.info(f"Tarea {task_id}: Configurando descarga de video")
                    stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
                    if not stream:
                        raise Exception("No se encontró stream de video")
                        
                    download_path = stream.download(output_path=DOWNLOAD_FOLDER, filename=f"{unique_filename}.mp4")
                
                logger.info(f"Tarea {task_id}: Contenido descargado en {download_path}")
                
            except Exception as e:
                error_msg = f"Error al descargar de YouTube: {str(e)}"
                logger.error(f"Tarea {task_id}: {error_msg}")
                
                # Si es un error 429, esperar y reintentar
                if "HTTP Error 429" in str(e):
                    wait_time = random.randint(5, 15)  # Esperar entre 5 y 15 segundos
                    logger.info(f"Tarea {task_id}: Esperando {wait_time} segundos antes de reintentar")
                    time.sleep(wait_time)
                    return self.retry(exc=e, countdown=wait_time)
                
                task_status[task_id] = {"status": "error", "message": error_msg}
                return {"status": "error", "message": error_msg}
        
        elif 'tiktok.com' in url:
            logger.info(f"Tarea {task_id}: Detectada URL de TikTok")
            ydl_opts = {
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, f"{unique_filename}.%(ext)s"),
                'verbose': True,
                'no_warnings': False,
                'retries': 10,
                'fragment_retries': 10,
                'skip_download_archive': True,
                'extractor_retries': 3,
                'ignoreerrors': True,
                'no_check_certificate': True,
                'prefer_insecure': True,
                'geo_bypass': True,
                'geo_verification_proxy': None,
                'http_headers': {
                    'User-Agent': get_random_user_agent(),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-us,en;q=0.5',
                    'Sec-Fetch-Mode': 'navigate',
                    'DNT': '1',
                    'Upgrade-Insecure-Requests': '1',
                    'Cache-Control': 'max-age=0',
                    'Connection': 'keep-alive',
                },
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info_dict)
                download_path = filename
                logger.info(f"Tarea {task_id}: Video de TikTok descargado en {download_path}")
        
        else:
            logger.info(f"Tarea {task_id}: Iniciando descarga genérica con yt-dlp")
            ydl_opts = {
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, f"{unique_filename}.%(ext)s"),
                'verbose': True,
                'no_warnings': False,
                'retries': 10,
                'fragment_retries': 10,
                'skip_download_archive': True,
                'extractor_retries': 3,
                'ignoreerrors': True,
                'no_check_certificate': True,
                'prefer_insecure': True,
                'geo_bypass': True,
                'geo_verification_proxy': None,
                'http_headers': {
                    'User-Agent': get_random_user_agent(),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-us,en;q=0.5',
                    'Sec-Fetch-Mode': 'navigate',
                    'DNT': '1',
                    'Upgrade-Insecure-Requests': '1',
                    'Cache-Control': 'max-age=0',
                    'Connection': 'keep-alive',
                },
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info_dict)
                download_path = filename
                logger.info(f"Tarea {task_id}: Contenido descargado en {download_path}")
        
        if not download_path or not os.path.exists(download_path):
            error_msg = f"No se encontró el archivo descargado: {download_path}"
            logger.error(f"Tarea {task_id}: {error_msg}")
            task_status[task_id] = {
                "status": "error", 
                "message": error_msg
            }
            return {"status": "error", "message": error_msg}
            
        logger.info(f"Tarea {task_id}: Descarga completada exitosamente")
        
        # Construir la URL de descarga
        download_url = f"/api/file/{os.path.basename(download_path)}"
        
        result = {
            "status": "success",
            "message": "Descarga completada",
            "download_url": download_url,
            "filename": os.path.basename(download_path)
        }
        
        task_status[task_id] = result
        return result
        
    except Exception as e:
        error_msg = f"Error al descargar: {str(e)}"
        logger.error(f"Tarea {task_id}: {error_msg}")
        
        # Si es un error 429, reintentar
        if "HTTP Error 429" in str(e):
            try:
                wait_time = random.randint(5, 15)  # Esperar entre 5 y 15 segundos
                logger.info(f"Tarea {task_id}: Esperando {wait_time} segundos antes de reintentar")
                time.sleep(wait_time)
                return self.retry(exc=e, countdown=wait_time)
            except self.MaxRetriesExceededError:
                error_msg = "Demasiados intentos fallidos. Por favor, inténtalo de nuevo más tarde."
        
        task_status[task_id] = {"status": "error", "message": error_msg}
        return {"status": "error", "message": error_msg}

@app.route('/api/download', methods=['POST'])
def download():
    try:
        logger.info("Recibida solicitud de descarga")
        data = request.json
        
        if not data or 'url' not in data:
            return jsonify({"status": "error", "message": "URL no proporcionada"}), 400
            
        url = data['url']
        media_type = data.get('type', 'video')  # Por defecto, descargar video
        quality = data.get('quality', None)
        
        logger.info(f"Iniciando descarga para URL: {url}, tipo: {media_type}, calidad: {quality}")
        
        # Iniciar tarea de Celery
        task = download_task.delay(url, media_type, quality)
        task_id = task.id
        logger.info(f"Tarea creada con ID: {task_id}")
        
        # Guardar estado inicial
        task_status[task_id] = {"status": "processing", "message": "La descarga ha comenzado"}
        
        return jsonify({
            "status": "processing",
            "task_id": task_id,
            "message": "La descarga ha comenzado. Usa el endpoint /api/status/{task_id} para verificar el estado."
        })
        
    except Exception as e:
        logger.error(f"Error al procesar la solicitud: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/status/<task_id>', methods=['GET'])
def task_status_route(task_id):
    try:
        logger.info(f"Verificando estado de tarea: {task_id}")
        
        # Primero verificar nuestro diccionario local
        if task_id in task_status:
            logger.info(f"Estado de tarea {task_id} encontrado en caché local: {task_status[task_id]}")
            return jsonify(task_status[task_id])
            
        # Si no está en el diccionario local, verificar en Celery
        task = download_task.AsyncResult(task_id)
        logger.info(f"Estado de tarea {task_id} en Celery: {task.state}")
        
        if task.state == 'PENDING':
            response = {
                "status": "processing",
                "message": "La tarea está pendiente",
                "task_id": task_id
            }
        elif task.state == 'SUCCESS':
            if task.result.get('status') == 'error':
                response = {
                    "status": "error",
                    "message": task.result.get('message', 'Error desconocido')
                }
            else:
                response = {
                    "status": "success",
                    "message": "Descarga completada",
                    "download_url": task.result.get('download_url'),
                    "filename": task.result.get('filename')
                }
        elif task.state == 'FAILURE':
            response = {
                "status": "error",
                "message": str(task.result) if task.result else "La tarea falló"
            }
        else:
            response = {
                "status": "processing",
                "message": f"Estado de la tarea: {task.state}",
                "task_id": task_id
            }
        
        logger.info(f"Estado de tarea {task_id} desde Celery: {response['status']}")
        # Actualizar nuestro diccionario local
        task_status[task_id] = response
        return jsonify(response)
        
    except Exception as e:
        error_msg = f"Error al verificar estado: {str(e)}"
        logger.error(error_msg)
        return jsonify({
            "status": "error",
            "message": error_msg
        }), 500

@app.route('/api/file/<filename>', methods=['GET'])
def download_file(filename):
    try:
        logger.info(f"Solicitud de descarga de archivo: {filename}")
        file_path = os.path.join(DOWNLOAD_FOLDER, filename)
        
        if not os.path.exists(file_path):
            logger.error(f"Archivo no encontrado: {file_path}")
            return jsonify({"status": "error", "message": "Archivo no encontrado"}), 404
            
        return send_file(file_path, as_attachment=True)
        
    except Exception as e:
        logger.error(f"Error al descargar archivo: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/', methods=['GET'])
def home():
    return """
    <h1>API de descarga de videos</h1>
    <p>Usa el endpoint /api/download para iniciar una descarga.</p>
    """

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)