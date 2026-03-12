import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from app.auth import require_api_key
from app.config import settings
from app.services import file_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    platform: Optional[str] = Form(None),
    _: str = Depends(require_api_key),
):
    """
    Subir archivo al servicio.

    Headers requeridos: X-API-Key

    Body: multipart/form-data
      - file: archivo a subir
      - platform: (opcional) whatsapp | facebook | instagram

    Respuesta:
      {
        "file_id": "abc123",
        "filename": "imagen.jpg",
        "content_type": "image/jpeg",
        "size_bytes": 102400,
        "share_url": "https://files.crm.../s/{token}",
        "share_token": "{token}",
        "internal_url": "https://files.crm.../f/{file_id}"
      }
    """
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    data = await file.read()

    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Archivo demasiado grande. Máximo: {settings.MAX_UPLOAD_MB}MB",
        )

    if not data:
        raise HTTPException(status_code=400, detail="Archivo vacío")

    try:
        result = file_service.upload_file(
            data=data,
            filename=file.filename or "archivo",
            content_type=file.content_type,
            platform=platform,
        )
        return result
    except Exception as e:
        logger.error(f"❌ Error en upload: {e}")
        raise HTTPException(status_code=500, detail=f"Error al subir archivo: {str(e)}")


@router.post("/share/{file_id}")
async def create_share_token(
    file_id: str,
    hours: int = 48,
    _: str = Depends(require_api_key),
):
    """
    Crear nuevo share token para un archivo existente.

    Parámetros:
      - file_id: ID del archivo
      - hours: duración del token (default 48h)

    Respuesta: {"share_url": "https://files.crm.../s/{token}"}
    """
    share_url = file_service.create_share_token(file_id, hours)
    if not share_url:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return {"share_url": share_url}


@router.get("/info/{file_id}")
async def get_file_info(
    file_id: str,
    _: str = Depends(require_api_key),
):
    """Obtener metadata de un archivo (acceso interno)."""
    record = file_service.get_file_by_id(file_id)
    if not record:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return record


@router.delete("/tokens/cleanup")
async def cleanup_expired_tokens(_: str = Depends(require_api_key)):
    """Eliminar tokens expirados. Llamar periódicamente."""
    count = file_service.cleanup_expired_tokens()
    return {"deleted_tokens": count}
