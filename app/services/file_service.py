import uuid
import mimetypes
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from app.database import get_db
from app.config import settings
from app.services import storage_service

logger = logging.getLogger(__name__)


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _expires_at(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")


def _build_relative_path(filename: str) -> str:
    """Construye ruta relativa con estructura de fecha: YYYY/MM/DD/{uuid}_{filename}"""
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
    Guardar archivo en el volumen y registrar en DB.

    Returns:
        {file_id, file_path, filename, content_type, size_bytes, share_url, share_token, internal_url}
    """
    if not content_type:
        content_type, _ = mimetypes.guess_type(filename)
        content_type = content_type or "application/octet-stream"

    relative_path = _build_relative_path(filename)
    file_id = uuid.uuid4().hex

    storage_service.save_file(relative_path, data)

    with get_db() as db:
        db.execute(
            """INSERT INTO file_records (id, s3_key, filename, content_type, size_bytes, platform, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (file_id, relative_path, filename, content_type, len(data), platform, _now_utc()),
        )

    token = _create_token(file_id, settings.SHARE_TOKEN_HOURS)
    share_url = f"{settings.PUBLIC_URL.rstrip('/')}/s/{token}"
    internal_url = f"{settings.PUBLIC_URL.rstrip('/')}/f/{file_id}"

    logger.info(f"✅ Archivo registrado: {file_id} → {relative_path}")

    return {
        "file_id": file_id,
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
    Obtener info del archivo dado un share token válido (no expirado).
    Incrementa el contador de descargas.
    """
    now = _now_utc()
    with get_db() as db:
        row = db.execute(
            """SELECT fr.id, fr.s3_key AS file_path, fr.filename, fr.content_type,
                      st.token, st.expires_at
               FROM share_tokens st
               JOIN file_records fr ON st.file_id = fr.id
               WHERE st.token = ? AND st.expires_at > ?""",
            (token, now),
        ).fetchone()

        if not row:
            return None

        db.execute(
            "UPDATE share_tokens SET download_count = download_count + 1 WHERE token = ?",
            (token,),
        )

    return {
        "file_id": row["id"],
        "file_path": row["file_path"],
        "filename": row["filename"],
        "content_type": row["content_type"],
    }


def get_file_by_id(file_id: str) -> Optional[dict]:
    """Obtener info del archivo por file_id (acceso interno autenticado)."""
    with get_db() as db:
        row = db.execute(
            "SELECT id, s3_key AS file_path, filename, content_type, size_bytes FROM file_records WHERE id = ?",
            (file_id,),
        ).fetchone()
    if not row:
        return None
    return dict(row)


def cleanup_expired_tokens() -> int:
    """Eliminar tokens expirados. Retorna cantidad eliminada."""
    now = _now_utc()
    with get_db() as db:
        cursor = db.execute("DELETE FROM share_tokens WHERE expires_at <= ?", (now,))
        count = cursor.rowcount
    if count:
        logger.info(f"🧹 Eliminados {count} tokens expirados")
    return count


def schedule_delete(file_id: str, hours: int = 48) -> bool:
    """
    Marcar un archivo para eliminación automática en `hours` horas.
    Llamar al cerrar una conversación para que el archivo se elimine
    cuando expire el share token (lazy deletion sin cron jobs).
    Retorna True si el archivo existe y fue marcado.
    """
    delete_at = _expires_at(hours)
    with get_db() as db:
        cursor = db.execute(
            "UPDATE file_records SET scheduled_delete_at = ? WHERE id = ?",
            (delete_at, file_id),
        )
    if cursor.rowcount:
        logger.info(f"🗓️ Archivo {file_id} marcado para eliminación en {hours}h ({delete_at})")
        return True
    logger.warning(f"⚠️ schedule_delete: archivo no encontrado: {file_id}")
    return False


def run_lazy_cleanup() -> int:
    """
    Eliminar archivos cuyo scheduled_delete_at ha vencido.
    Se llama en cada request (lazy deletion). No bloquea: se ejecuta
    en hilo separado vía loop.run_in_executor desde el middleware.
    Retorna cantidad de archivos físicamente eliminados.
    """
    now = _now_utc()
    with get_db() as db:
        rows = db.execute(
            """SELECT id, s3_key FROM file_records
               WHERE scheduled_delete_at IS NOT NULL AND scheduled_delete_at <= ?""",
            (now,),
        ).fetchall()

    if not rows:
        return 0

    deleted = 0
    for row in rows:
        try:
            storage_service.delete_file(row["s3_key"])
            with get_db() as db:
                db.execute("DELETE FROM file_records WHERE id = ?", (row["id"],))
            deleted += 1
            logger.info(f"🗑️ [LAZY-DELETE] Archivo eliminado: {row['id']} ({row['s3_key']})")
        except Exception as e:
            logger.error(f"❌ [LAZY-DELETE] Error eliminando {row['id']}: {e}")

    if deleted:
        logger.info(f"🧹 [LAZY-DELETE] {deleted} archivo(s) eliminado(s)")
    return deleted

