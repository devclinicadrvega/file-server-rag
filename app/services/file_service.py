import uuid
import hashlib
import mimetypes
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from app.database import get_db
from app.config import settings
from app.services import s3_service

logger = logging.getLogger(__name__)


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _expires_at(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")


def _build_s3_key(filename: str) -> str:
    """Construye la clave S3 con estructura de fecha: YYYY/MM/DD/{uuid}_{filename}"""
    now = datetime.now(timezone.utc)
    unique_id = uuid.uuid4().hex[:12]
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
    return f"{now.year:04d}/{now.month:02d}/{now.day:02d}/{unique_id}_{safe_name}"


def upload_file(
    data: bytes,
    filename: str,
    content_type: Optional[str] = None,
    platform: Optional[str] = None,
) -> dict:
    """
    Subir archivo a S3 y registrar en DB.

    Returns:
        {file_id, s3_key, filename, content_type, size_bytes, share_url, internal_url}
    """
    if not content_type:
        content_type, _ = mimetypes.guess_type(filename)
        content_type = content_type or "application/octet-stream"

    s3_key = _build_s3_key(filename)
    file_id = uuid.uuid4().hex

    s3_service.upload_file(data=data, s3_key=s3_key, content_type=content_type)

    with get_db() as db:
        db.execute(
            """INSERT INTO file_records (id, s3_key, filename, content_type, size_bytes, platform, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (file_id, s3_key, filename, content_type, len(data), platform, _now_utc()),
        )

    # Generar share token por defecto (48h)
    token = _create_token(file_id, settings.SHARE_TOKEN_HOURS)
    share_url = f"{settings.PUBLIC_URL.rstrip('/')}/s/{token}"
    internal_url = f"{settings.PUBLIC_URL.rstrip('/')}/f/{file_id}"

    logger.info(f"✅ Archivo registrado: {file_id} → {s3_key}")

    return {
        "file_id": file_id,
        "s3_key": s3_key,
        "filename": filename,
        "content_type": content_type,
        "size_bytes": len(data),
        "share_url": share_url,
        "share_token": token,
        "internal_url": internal_url,
    }


def _create_token(file_id: str, hours: int) -> str:
    """Crear share token en DB y retornar el token string."""
    token = uuid.uuid4().hex
    expires_at = _expires_at(hours)
    with get_db() as db:
        db.execute(
            "INSERT INTO share_tokens (token, file_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (token, file_id, expires_at, _now_utc()),
        )
    return token


def create_share_token(file_id: str, hours: Optional[int] = None) -> Optional[str]:
    """
    Crear nuevo share token para un file_id existente.
    Retorna la URL pública o None si el archivo no existe.
    """
    hours = hours or settings.SHARE_TOKEN_HOURS
    with get_db() as db:
        row = db.execute("SELECT id FROM file_records WHERE id = ?", (file_id,)).fetchone()
        if not row:
            return None
    token = _create_token(file_id, hours)
    return f"{settings.PUBLIC_URL.rstrip('/')}/s/{token}"


def get_file_by_token(token: str) -> Optional[dict]:
    """
    Obtener info del archivo dado un share token.
    Valida que no haya expirado.
    Returns dict con {file_id, s3_key, filename, content_type} o None.
    """
    now = _now_utc()
    with get_db() as db:
        row = db.execute(
            """SELECT fr.id, fr.s3_key, fr.filename, fr.content_type, st.token, st.expires_at
               FROM share_tokens st
               JOIN file_records fr ON st.file_id = fr.id
               WHERE st.token = ? AND st.expires_at > ?""",
            (token, now),
        ).fetchone()

        if not row:
            return None

        # Incrementar contador
        db.execute(
            "UPDATE share_tokens SET download_count = download_count + 1 WHERE token = ?",
            (token,),
        )

    return {
        "file_id": row["id"],
        "s3_key": row["s3_key"],
        "filename": row["filename"],
        "content_type": row["content_type"],
    }


def get_file_by_id(file_id: str) -> Optional[dict]:
    """Obtener info del archivo por file_id (acceso interno autenticado)."""
    with get_db() as db:
        row = db.execute(
            "SELECT id, s3_key, filename, content_type, size_bytes FROM file_records WHERE id = ?",
            (file_id,),
        ).fetchone()
    if not row:
        return None
    return dict(row)


def get_presigned_url(file_id: str, expires_seconds: int = 3600) -> Optional[str]:
    """Generar presigned S3 URL para un file_id (útil para FB/IG adjunto directo)."""
    record = get_file_by_id(file_id)
    if not record:
        return None
    return s3_service.generate_presigned_url(record["s3_key"], expires_seconds)


def cleanup_expired_tokens() -> int:
    """Eliminar tokens expirados. Retorna cantidad eliminada."""
    now = _now_utc()
    with get_db() as db:
        cursor = db.execute("DELETE FROM share_tokens WHERE expires_at <= ?", (now,))
        count = cursor.rowcount
    if count:
        logger.info(f"🧹 Eliminados {count} tokens expirados")
    return count
