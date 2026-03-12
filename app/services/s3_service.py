import boto3
import io
import logging
import mimetypes
from botocore.exceptions import ClientError
from botocore.config import Config
from app.config import settings

logger = logging.getLogger(__name__)


def _get_client():
    """Crear cliente S3 boto3 compatible con Coolify S3 / MinIO / AWS."""
    kwargs = {
        "aws_access_key_id": settings.S3_ACCESS_KEY_ID,
        "aws_secret_access_key": settings.S3_SECRET_ACCESS_KEY,
        "region_name": settings.S3_REGION,
        "config": Config(signature_version="s3v4"),
    }
    if settings.S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL

    return boto3.client("s3", **kwargs)


def ensure_bucket_exists():
    """Crear el bucket si no existe (solo en MinIO/compatible, en AWS ya debe existir)."""
    try:
        client = _get_client()
        try:
            client.head_bucket(Bucket=settings.S3_BUCKET_NAME)
            logger.info(f"✅ Bucket '{settings.S3_BUCKET_NAME}' existe")
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchBucket"):
                client.create_bucket(Bucket=settings.S3_BUCKET_NAME)
                logger.info(f"✅ Bucket '{settings.S3_BUCKET_NAME}' creado")
            else:
                raise
    except Exception as e:
        logger.warning(f"⚠️ No se pudo verificar/crear bucket: {e}")


def upload_file(
    data: bytes,
    s3_key: str,
    content_type: str = "application/octet-stream",
) -> bool:
    """Subir archivo a S3. Retorna True si exitoso."""
    try:
        client = _get_client()
        client.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=s3_key,
            Body=data,
            ContentType=content_type,
            # Privado por defecto — acceso solo via presigned URL o el servicio
        )
        logger.info(f"✅ Subido a S3: {s3_key} ({len(data)} bytes)")
        return True
    except Exception as e:
        logger.error(f"❌ Error subiendo a S3: {e}")
        raise


def download_file(s3_key: str) -> bytes:
    """Descargar archivo de S3. Retorna bytes."""
    try:
        client = _get_client()
        response = client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        data = response["Body"].read()
        logger.info(f"✅ Descargado de S3: {s3_key} ({len(data)} bytes)")
        return data
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            raise FileNotFoundError(f"Archivo no encontrado en S3: {s3_key}")
        raise


def generate_presigned_url(s3_key: str, expires_seconds: int = 3600) -> str:
    """
    Generar URL firmada temporal para acceso directo a S3.
    Útil para intentar envío directo a Facebook/Instagram.
    """
    try:
        client = _get_client()
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET_NAME, "Key": s3_key},
            ExpiresIn=expires_seconds,
        )
        # Si hay PUBLIC_URL distinto al endpoint, reemplazar host
        if settings.S3_PUBLIC_URL and settings.S3_ENDPOINT_URL:
            url = url.replace(
                settings.S3_ENDPOINT_URL.rstrip("/"),
                settings.S3_PUBLIC_URL.rstrip("/"),
            )
        return url
    except Exception as e:
        logger.error(f"❌ Error generando presigned URL: {e}")
        raise


def delete_file(s3_key: str) -> bool:
    """Eliminar archivo de S3."""
    try:
        client = _get_client()
        client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        logger.info(f"🗑️ Eliminado de S3: {s3_key}")
        return True
    except Exception as e:
        logger.warning(f"⚠️ Error eliminando de S3: {e}")
        return False
