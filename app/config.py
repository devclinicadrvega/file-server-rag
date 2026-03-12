import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8002
    DEBUG: bool = False

    # API Key para autenticación interna (el backend la usa)
    API_KEY: str = "change-me-in-production"

    # S3 / Coolify S3 (compatible con boto3)
    S3_ENDPOINT_URL: str = ""          # ej: https://s3.crm.clinicadrvega.com
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_BUCKET_NAME: str = "file-server"
    S3_REGION: str = "us-east-1"       # requerido por boto3, cualquier valor sirve
    S3_PUBLIC_URL: str = ""            # si S3 tiene URL pública distinta al endpoint

    # Base URL pública del servicio (para generar share links)
    PUBLIC_URL: str = "https://files.crm.clinicadrvega.com"

    # Tokens de compartir
    SHARE_TOKEN_HOURS: int = 48        # duración por defecto de share tokens
    MAX_UPLOAD_MB: int = 50            # tamaño máximo de archivo en MB

    # SQLite
    DB_PATH: str = "/data/fileserver.db"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
