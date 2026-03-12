import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8002
    DEBUG: bool = False

    # API Key para autenticación interna (el backend la usa)
    API_KEY: str = "change-me-in-production"

    # Almacenamiento local (volumen Coolify Persistent Storage)
    STORAGE_PATH: str = "/data/files"   # donde se guardan los archivos
    DB_PATH: str = "/data/fileserver.db"

    # URL pública del servicio (para generar share links)
    PUBLIC_URL: str = "https://files.crm.clinicadrvega.com"

    # Tokens de compartir
    SHARE_TOKEN_HOURS: int = 48         # duración por defecto de share tokens
    MAX_UPLOAD_MB: int = 50             # tamaño máximo de archivo en MB

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
