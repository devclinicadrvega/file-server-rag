import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.services.storage_service import ensure_storage
from app.api import internal, public

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Iniciando file-server...")
    init_db()
    logger.info("✅ Base de datos inicializada")
    ensure_storage()
    yield
    logger.info("🛑 file-server detenido")


app = FastAPI(
    title="File Server",
    description="Servicio de almacenamiento y compartición de archivos",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Rutas públicas (share links, file directo)
app.include_router(public.router, tags=["public"])

# Rutas internas (upload, share token creation, etc.)
app.include_router(internal.router, prefix="/api", tags=["internal"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "file-server"}


@app.get("/robots.txt", include_in_schema=False)
async def robots():
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("User-agent: *\nDisallow: /\n")


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
