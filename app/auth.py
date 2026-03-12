import logging
from functools import wraps
from fastapi import HTTPException, Header
from app.config import settings


logger = logging.getLogger(__name__)


def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """Dependencia FastAPI para validar API key interna."""
    if x_api_key != settings.API_KEY:
        logger.warning("⚠️ Intento de acceso con API key inválida")
        raise HTTPException(status_code=401, detail="API key inválida")
    return x_api_key
