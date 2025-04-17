import json
from yt_dlp import YoutubeDL
import os

def handler(event, context):
    try:
        body = json.loads(event['body'])
        url = body.get('url')
        download_type = body.get('type', 'video')

        quality = 'bestvideo+bestaudio' if download_type == 'video' else 'bestaudio/best'
        if 'tiktok.com' in url.lower() and download_type == 'video':
            quality = 'best'

        ydl_opts = {
            'format': quality,
            'noplaylist': True,
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'windowsfilenames': True,
        }

        if download_type == 'audio':
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else:
            ydl_opts['merge_output_format'] = 'mp4'

        os.makedirs('downloads', exist_ok=True)

        with YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(url, download=True)
            real_path = ydl.prepare_filename(result)
            if download_type == 'audio':
                real_path = os.path.splitext(real_path)[0] + ".mp3"

        basename = os.path.basename(real_path)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'success',
                'filename': basename,
                'metadata': {
                    'title': result.get('title'),
                    'author': result.get('uploader'),
                    'length': result.get('duration'),
                    'type': download_type
                }
            })
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'status': 'error', 'message': str(e)})
        }
