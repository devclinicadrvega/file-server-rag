import logging
from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import StreamingResponse, Response
from app.services import file_service
from app.services.s3_service import download_file
from app.auth import require_api_key
from fastapi import Depends
import io

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/s/{token}")
async def serve_share_link(token: str):
    """
    Servir archivo vía share token público (sin autenticación).
    El token expira según configuración (default 48h).
    """
    record = file_service.get_file_by_token(token)
    if not record:
        raise HTTPException(
            status_code=404,
            detail="Archivo no encontrado o enlace expirado",
        )

    try:
        data = download_file(record["s3_key"])
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Archivo no encontrado en almacenamiento")
    except Exception as e:
        logger.error(f"❌ Error descargando archivo {record['s3_key']}: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener archivo")

    filename = record["filename"]
    content_type = record["content_type"]

    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, max-age=3600",
            "Content-Length": str(len(data)),
        },
    )


@router.get("/f/{file_id}")
async def serve_internal_file(
    file_id: str,
    _: str = Depends(require_api_key),
):
    """
    Servir archivo por file_id (acceso interno autenticado).
    Usado por el frontend vía el backend proxy.
    """
    record = file_service.get_file_by_id(file_id)
    if not record:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    try:
        data = download_file(record["s3_key"])
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Archivo no encontrado en almacenamiento")
    except Exception as e:
        logger.error(f"❌ Error descargando archivo {record['s3_key']}: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener archivo")

    return Response(
        content=data,
        media_type=record["content_type"],
        headers={
            "Content-Disposition": f'inline; filename="{record["filename"]}"',
            "Cache-Control": "private, max-age=300",
            "Content-Length": str(len(data)),
        },
    )
