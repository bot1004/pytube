<div align="center">
  <p>
    <a href="#"><img src="https://assets.nickficano.com/gh-pytube.min.svg" width="456" height="143" alt="pytube logo" /></a>
  </p>
  <p align="center">
	<a href="https://pypi.org/project/pytube/"><img src="https://img.shields.io/pypi/dm/pytube?style=flat-square" alt="pypi"/></a>
	<a href="https://pytube.io/en/latest/"><img src="https://readthedocs.org/projects/python-pytube/badge/?version=latest&style=flat-square" /></a>
	<a href="https://pypi.org/project/pytube/"><img src="https://img.shields.io/pypi/v/pytube?style=flat-square" /></a>
  </p>
</div>

### Actively soliciting contributors!

Have ideas for how pytube can be improved? Feel free to open an issue or a pull request!

# pytube

*pytube* is a genuine, lightweight, dependency-free Python library (and command-line utility) for downloading YouTube videos.

## Documentation

Detailed documentation about the usage of the library can be found at [pytube.io](https://pytube.io). This is recommended for most cases. If you want to hastily download a single video, the [quick start](#Quickstart) guide below might be what you're looking for.

## Description

YouTube is the most popular video-sharing platform in the world and as a hacker, you may encounter a situation where you want to script something to download videos. For this, I present to you: *pytube*.

*pytube* is a lightweight library written in Python. It has no third-party
dependencies and aims to be highly reliable.

*pytube* also makes pipelining easy, allowing you to specify callback functions for different download events, such as  ``on progress`` or ``on complete``.

Furthermore, *pytube* includes a command-line utility, allowing you to download videos right from the terminal.

## Features

- Support for both progressive & DASH streams
- Support for downloading the complete playlist
- Easily register ``on_download_progress`` & ``on_download_complete`` callbacks
- Command-line interfaced included
- Caption track support
- Outputs caption tracks to .srt format (SubRip Subtitle)
- Ability to capture thumbnail URL
- Extensively documented source code
- No third-party dependencies

## Quickstart

This guide covers the most basic usage of the library. For more detailed information, please refer to [pytube.io](https://pytube.io).

### Installation

Pytube requires an installation of Python 3.6 or greater, as well as pip. (Pip is typically bundled with Python [installations](https://python.org/downloads).)

To install from PyPI with pip:

```bash
$ python -m pip install pytube
```

Sometimes, the PyPI release becomes slightly outdated. To install from the source with pip:

```bash
$ python -m pip install git+https://github.com/pytube/pytube
```

### Using pytube in a Python script

To download a video using the library in a script, you'll need to import the YouTube class from the library and pass an argument of the video URL. From there, you can access the streams and download them.

```python
 >>> from pytube import YouTube
 >>> YouTube('https://youtu.be/2lAe1cqCOXo').streams.first().download()
 >>> yt = YouTube('http://youtube.com/watch?v=2lAe1cqCOXo')
 >>> yt.streams
  ... .filter(progressive=True, file_extension='mp4')
  ... .order_by('resolution')
  ... .desc()
  ... .first()
  ... .download()
```

### Using the command-line interface

Using the CLI is remarkably straightforward as well. To download a video at the highest progressive quality, you can use the following command:
```bash
$ pytube https://youtube.com/watch?v=2lAe1cqCOXo
```

You can also do the same for a playlist:
```bash
$ pytube https://www.youtube.com/playlist?list=PLS1QulWo1RIaJECMeUT4LFwJ-ghgoSH6n
```

# API de Descarga de Videos y Audio

Esta API permite descargar videos y audio de múltiples plataformas como YouTube, Instagram, TikTok, Twitter, Facebook, Vimeo, Dailymotion y Reddit.

## Requisitos Previos

1. Python 3.8 o superior
2. pip (gestor de paquetes de Python)
3. FFmpeg instalado en el sistema

## Instalación

1. Clona el repositorio:
```bash
git clone <url-del-repositorio>
cd <nombre-del-directorio>
```

2. Instala las dependencias:
```bash
pip install -r requirements.txt
```

3. Instala FFmpeg:
   - Windows: Descarga desde [ffmpeg.org](https://ffmpeg.org/download.html)
   - Linux: `sudo apt-get install ffmpeg`
   - macOS: `brew install ffmpeg`

## Configuración

1. Crea un archivo `.env` en la raíz del proyecto con las siguientes variables:
```env
BOT_TOKEN=tu_token_de_telegram
N8N_UPLOAD_URL=url_de_tu_servicio_n8n (opcional)
PORT=5000
```

2. Crea un directorio `downloads` en la raíz del proyecto:
```bash
mkdir downloads
```

## Uso de la API

### Endpoint de Descarga

```
POST /api/download
```

### Headers Requeridos
```
Content-Type: application/json
```

### Body de la Petición
```json
{
    "url": "URL_DEL_VIDEO",
    "type": "video" // o "audio"
}
```

### Ejemplo de Uso con Postman

1. Abre Postman
2. Crea una nueva petición POST
3. URL: `https://pytube-zcjp.onrender.com/api/download`
4. Headers:
   - Key: `Content-Type`
   - Value: `application/json`
5. Body (raw JSON):
```json
{
    "url": "https://www.youtube.com/watch?v=ejemplo",
    "type": "video"
}
```

### Ejemplo de Uso con cURL

```bash
curl -X POST https://pytube-zcjp.onrender.com/api/download \
-H "Content-Type: application/json" \
-d '{"url": "https://www.youtube.com/watch?v=ejemplo", "type": "video"}'
```

### Ejemplo de Uso con n8n

1. Crea un nuevo workflow en n8n
2. Añade un nodo "HTTP Request"
3. Configura el nodo:
   - Method: POST
   - URL: `https://pytube-zcjp.onrender.com/api/download`
   - Headers: `Content-Type: application/json`
   - Body: 
   ```json
   {
       "url": "{{$node["Previous Node"].json.url}}",
       "type": "{{$node["Previous Node"].json.type}}"
   }
   ```

## Respuesta de la API

### Respuesta Exitosa
```json
{
    "status": "success",
    "filename": "nombre_del_archivo",
    "metadata": {
        "title": "título del video",
        "author": "autor",
        "length": "duración en segundos",
        "type": "tipo de descarga"
    }
}
```

### Respuesta de Error
```json
{
    "status": "error",
    "message": "descripción del error"
}
```

## Plataformas Soportadas

- YouTube 📺
- Instagram 📸
- TikTok 🎵
- Twitter 🐦
- Facebook 👍
- Vimeo 🎞️
- Dailymotion 📹
- Reddit 👽

## Limitaciones

1. Tamaño máximo de archivo: 50MB
2. Para archivos mayores a 50MB, se requiere configurar `N8N_UPLOAD_URL`
3. Timeout de descarga: 120 segundos

## Solución de Problemas

1. **Error de FFmpeg**: Asegúrate de que FFmpeg está instalado y accesible en el PATH del sistema
2. **Error de permisos**: Verifica que el directorio `downloads` tiene permisos de escritura
3. **Error de timeout**: Aumenta el valor de `timeout` en `gunicorn_config.py` si es necesario

## Contribuir

Las contribuciones son bienvenidas. Por favor, abre un issue para discutir los cambios propuestos.

## Licencia

Este proyecto está bajo la Licencia MIT.
