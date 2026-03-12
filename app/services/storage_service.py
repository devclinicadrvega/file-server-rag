import os
import logging
from app.config import settings

logger = logging.getLogger(__name__)


def ensure_storage():
    """Crear directorio de almacenamiento si no existe."""
    os.makedirs(settings.STORAGE_PATH, exist_ok=True)
    logger.info(f"✅ Almacenamiento en: {settings.STORAGE_PATH}")


def get_file_path(relative_path: str) -> str:
    """Retorna la ruta absoluta de un archivo dado su path relativo."""
    return os.path.join(settings.STORAGE_PATH, relative_path)


def save_file(relative_path: str, data: bytes) -> int:
    """
    Guardar archivo en el volumen.

    Args:
        relative_path: ruta relativa dentro de STORAGE_PATH (ej: "2026/03/12/abc_foto.jpg")
        data: bytes del archivo

    Returns:
        Cantidad de bytes escritos
    """
    full_path = get_file_path(relative_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "wb") as f:
        f.write(data)
    logger.info(f"💾 Guardado: {relative_path} ({len(data)} bytes)")
    return len(data)


def read_file(relative_path: str) -> bytes:
    """
    Leer archivo del volumen.

    Raises:
        FileNotFoundError si no existe
    """
    full_path = get_file_path(relative_path)
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Archivo no encontrado: {relative_path}")
    with open(full_path, "rb") as f:
        return f.read()


def delete_file(relative_path: str) -> bool:
    """Eliminar archivo del volumen. Retorna True si existía."""
    full_path = get_file_path(relative_path)
    if os.path.exists(full_path):
        os.remove(full_path)
        logger.info(f"🗑️ Eliminado: {relative_path}")
        return True
    return False


def file_exists(relative_path: str) -> bool:
    return os.path.exists(get_file_path(relative_path))
