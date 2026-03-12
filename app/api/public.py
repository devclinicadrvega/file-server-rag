import os
import logging
from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import Response, StreamingResponse
from app.services import file_service
from app.services.storage_service import read_file, get_file_path
from app.auth import require_api_key
from fastapi import Depends

logger = logging.getLogger(__name__)
router = APIRouter()


def _stream_file(full_path: str, chunk_size: int = 65536):
    """Generator que sirve el archivo en chunks para evitar cargar todo en memoria."""
    with open(full_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk


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

    full_path = get_file_path(record["file_path"])
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado en almacenamiento")

    file_size = os.path.getsize(full_path)

    return StreamingResponse(
        _stream_file(full_path),
        media_type=record["content_type"],
        headers={
            "Content-Disposition": f'inline; filename="{record["filename"]}"',
            "Cache-Control": "public, max-age=86400",
            "Content-Length": str(file_size),
        },
    )


@router.get("/f/{file_id}")
async def serve_internal_file(
    file_id: str,
    _: str = Depends(require_api_key),
):
    """
    Servir archivo por file_id (acceso interno autenticado con X-API-Key).
    Usado por el backend para mostrar imágenes al frontend.
    """
    record = file_service.get_file_by_id(file_id)
    if not record:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    full_path = get_file_path(record["file_path"])
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado en almacenamiento")

    file_size = os.path.getsize(full_path)

    return StreamingResponse(
        _stream_file(full_path),
        media_type=record["content_type"],
        headers={
            "Content-Disposition": f'inline; filename="{record["filename"]}"',
            "Cache-Control": "private, max-age=300",
            "Content-Length": str(file_size),
        },
    )

