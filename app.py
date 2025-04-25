import os
import uuid
import logging
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from celery import Celery
import yt_dlp
import pytube
import instaloader
import time

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializar Flask
app = Flask(__name__)
CORS(app)

# Configuración de Celery con variables de entorno para Render.com
# Asegurarse de que la URL de Redis tenga el formato correcto
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# Asegurarse de que la URL comienza con 'redis://'
if not redis_url.startswith('redis://') and not redis_url.startswith('rediss://'):
    redis_url = 'redis://' + redis_url

logger.info(f"Usando Redis URL: {redis_url}")

# Configuración de Celery (usando método recomendado para evitar warnings)
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

@celery.task(bind=True)
def download_task(self, url, media_type, quality=None):
    task_id = self.request.id
    task_status[task_id] = {"status": "processing", "message": "Iniciando descarga..."}
    logger.info(f"Tarea {task_id}: Iniciando descarga de {url}")
    
    try:
        filename = None
        download_path = None
        
        # Generar un nombre de archivo único
        unique_filename = f"{uuid.uuid4().hex}"
        
        if 'youtube.com' in url or 'youtu.be' in url:
            logger.info(f"Tarea {task_id}: Detectada URL de YouTube")
            
            if media_type == 'audio':
                # Descargar solo audio usando yt-dlp
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': os.path.join(DOWNLOAD_FOLDER, f"{unique_filename}.%(ext)s"),
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    logger.info(f"Tarea {task_id}: Ejecutando yt-dlp para audio")
                    info_dict = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info_dict)
                    # Cambiar la extensión a mp3 ya que el post-procesador lo convierte
                    base, _ = os.path.splitext(filename)
                    filename = f"{base}.mp3"
                    download_path = filename
                    logger.info(f"Tarea {task_id}: Audio descargado en {download_path}")
                    
            else:  # video
                logger.info(f"Tarea {task_id}: Usando pytube para video")
                # Usar pytube para videos
                yt = pytube.YouTube(url)
                
                if quality:
                    stream = yt.streams.filter(res=quality).first()
                    if not stream:
                        stream = yt.streams.get_highest_resolution()
                else:
                    stream = yt.streams.get_highest_resolution()
                
                logger.info(f"Tarea {task_id}: Stream seleccionado: {stream}")
                filename = f"{unique_filename}.mp4"
                download_path = os.path.join(DOWNLOAD_FOLDER, filename)
                stream.download(output_path=DOWNLOAD_FOLDER, filename=filename)
                logger.info(f"Tarea {task_id}: Video descargado en {download_path}")
                
        elif 'instagram.com' in url:
            logger.info(f"Tarea {task_id}: Detectada URL de Instagram")
            L = instaloader.Instaloader(
                dirname_pattern=DOWNLOAD_FOLDER,
                filename_pattern=unique_filename
            )
            
            if '/p/' in url:  # Es una publicación
                shortcode = url.split('/p/')[1].split('/')[0]
                post = instaloader.Post.from_shortcode(L.context, shortcode)
                L.download_post(post, target=unique_filename)
                
                # Encuentra el archivo descargado
                for file in os.listdir(DOWNLOAD_FOLDER):
                    if file.startswith(unique_filename):
                        if (media_type == 'video' and file.endswith('.mp4')) or \
                           (media_type == 'image' and (file.endswith('.jpg') or file.endswith('.png'))):
                            filename = file
                            download_path = os.path.join(DOWNLOAD_FOLDER, filename)
                            logger.info(f"Tarea {task_id}: Contenido de Instagram descargado en {download_path}")
                            break
            else:
                raise Exception("Solo se permiten enlaces directos a publicaciones de Instagram")
                
        elif 'tiktok.com' in url:
            logger.info(f"Tarea {task_id}: Detectada URL de TikTok")
            ydl_opts = {
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, f"{unique_filename}.%(ext)s"),
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info_dict)
                download_path = filename
                logger.info(f"Tarea {task_id}: Video de TikTok descargado en {download_path}")
                
        else:
            # Para otras plataformas, usar yt-dlp genérico
            logger.info(f"Tarea {task_id}: Iniciando descarga genérica con yt-dlp")
            ydl_opts = {
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, f"{unique_filename}.%(ext)s"),
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info_dict)
                download_path = filename
                logger.info(f"Tarea {task_id}: Contenido descargado en {download_path}")
        
        if not download_path or not os.path.exists(download_path):
            logger.error(f"Tarea {task_id}: No se encontró el archivo descargado: {download_path}")
            task_status[task_id] = {
                "status": "error", 
                "message": f"Error: No se pudo descargar el archivo"
            }
            return {"status": "error", "message": "No se pudo descargar el archivo"}
            
        logger.info(f"Tarea {task_id}: Descarga completada exitosamente")
        
        # Construir la URL de descarga
        download_url = f"/api/file/{os.path.basename(download_path)}"
        
        task_status[task_id] = {
            "status": "success",
            "message": "Descarga completada",
            "download_url": download_url,
            "filename": os.path.basename(download_path)
        }
        
        return {
            "status": "success",
            "message": "Descarga completada",
            "download_url": download_url,
            "filename": os.path.basename(download_path)
        }
        
    except Exception as e:
        logger.error(f"Tarea {task_id}: Error al descargar: {str(e)}")
        task_status[task_id] = {"status": "error", "message": f"Error: {str(e)}"}
        return {"status": "error", "message": str(e)}

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
            logger.info(f"Estado de tarea {task_id} encontrado en caché local")
            return jsonify(task_status[task_id])
            
        # Si no está en el diccionario local, verificar en Celery
        task = download_task.AsyncResult(task_id)
        
        if task.state == 'PENDING':
            response = {
                "status": "processing",
                "message": "La tarea está pendiente"
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
                "message": f"Estado de la tarea: {task.state}"
            }
        
        logger.info(f"Estado de tarea {task_id} desde Celery: {response['status']}")
        # Actualizar nuestro diccionario local
        task_status[task_id] = response
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error al verificar estado: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error al verificar estado: {str(e)}"
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