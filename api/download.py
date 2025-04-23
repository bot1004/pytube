import json

async def handler(request):
    try:
        data = await request.json()
        url = data.get('url')
        download_type = data.get('type', 'video')

        # Simulación simple de respuesta para pruebas
        return {
            "statusCode": 200,
            "body": json.dumps({
                "status": "ok",
                "message": f"Recibido enlace '{url}' para descargar como '{download_type}'"
            })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "status": "error",
                "message": str(e)
            })
        }
