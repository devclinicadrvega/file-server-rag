import os
import logging
from fastapi import APIRouter, HTTPException, Path, Request
from fastapi.responses import Response, StreamingResponse, HTMLResponse
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


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / 1024 / 1024:.1f} MB"


def _build_download_page(token: str, record: dict, file_size: int, base_url: str) -> str:
    """Genera la página HTML de descarga con preview y botón."""
    filename = record["filename"]
    content_type = record["content_type"]
    size_str = _format_size(file_size)
    download_url = f"{base_url}/s/{token}?download=1"
    file_url = f"{base_url}/s/{token}?raw=1"

    is_image = content_type.startswith("image/")
    is_video = content_type.startswith("video/")
    is_audio = content_type.startswith("audio/")

    if is_image:
        icon = "🖼️"
        type_label = "Imagen"
        preview_html = f"""
        <div class="preview">
          <img src="{file_url}" alt="{filename}" loading="lazy" />
        </div>"""
    elif is_video:
        icon = "🎥"
        type_label = "Video"
        preview_html = f"""
        <div class="preview">
          <video controls preload="metadata">
            <source src="{file_url}" type="{content_type}">
          </video>
        </div>"""
    elif is_audio:
        icon = "🎵"
        type_label = "Audio"
        preview_html = f"""
        <div class="preview audio-preview">
          <div class="audio-icon">🎵</div>
          <audio controls preload="metadata" style="width:100%;margin-top:16px">
            <source src="{file_url}" type="{content_type}">
          </audio>
        </div>"""
    else:
        icon = "📄"
        type_label = "Documento"
        preview_html = f"""
        <div class="preview file-preview">
          <div class="file-icon">📄</div>
          <p class="file-name">{filename}</p>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{icon} {filename}</title>
  <meta property="og:title" content="{filename}">
  <meta property="og:type" content="website">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #f0f2f5;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 24px 16px;
    }}
    .card {{
      background: white;
      border-radius: 20px;
      box-shadow: 0 4px 24px rgba(0,0,0,0.10);
      max-width: 480px;
      width: 100%;
      overflow: hidden;
    }}
    .header {{
      background: linear-gradient(135deg, #25D366 0%, #128C7E 100%);
      padding: 24px 24px 20px;
      color: white;
      text-align: center;
    }}
    .header h1 {{ font-size: 1.1rem; font-weight: 600; margin-top: 8px; word-break: break-word; }}
    .header p {{ font-size: 0.82rem; opacity: 0.85; margin-top: 4px; }}
    .preview {{
      background: #111;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 200px;
      max-height: 360px;
      overflow: hidden;
    }}
    .preview img {{
      max-width: 100%;
      max-height: 360px;
      object-fit: contain;
      display: block;
    }}
    .preview video {{
      max-width: 100%;
      max-height: 360px;
      display: block;
    }}
    .audio-preview, .file-preview {{
      background: #1a1a2e;
      padding: 40px 24px;
      flex-direction: column;
    }}
    .audio-icon, .file-icon {{ font-size: 4rem; text-align: center; }}
    .file-name {{
      color: #ccc;
      font-size: 0.9rem;
      text-align: center;
      margin-top: 12px;
      word-break: break-all;
    }}
    .body {{
      padding: 24px;
    }}
    .info {{
      display: flex;
      justify-content: space-between;
      font-size: 0.82rem;
      color: #888;
      margin-bottom: 20px;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .info span {{
      display: flex;
      align-items: center;
      gap: 4px;
    }}
    .btn-download {{
      display: block;
      width: 100%;
      padding: 16px;
      background: linear-gradient(135deg, #25D366 0%, #128C7E 100%);
      color: white;
      text-align: center;
      font-size: 1.1rem;
      font-weight: 700;
      text-decoration: none;
      border-radius: 12px;
      letter-spacing: 0.3px;
      box-shadow: 0 4px 12px rgba(37,211,102,0.35);
      transition: opacity 0.2s;
    }}
    .btn-download:hover {{ opacity: 0.92; }}
    .expiry-note {{
      font-size: 0.75rem;
      color: #aaa;
      text-align: center;
      margin-top: 14px;
    }}
    .expiry-note strong {{ color: #e67e22; }}
    .footer {{
      text-align: center;
      font-size: 0.72rem;
      color: #bbb;
      margin-top: 20px;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div style="font-size:2.2rem">{icon}</div>
      <h1>{filename}</h1>
      <p>{type_label} · {size_str}</p>
    </div>
    {preview_html}
    <div class="body">
      <div class="info">
        <span>📁 {type_label}</span>
        <span>💾 {size_str}</span>
        <span>⏱️ Disponible 48h</span>
      </div>
      <a href="{download_url}" class="btn-download">
        ⬇️ &nbsp; Descargar {type_label}
      </a>
      <p class="expiry-note">
        <strong>⚠️ Este enlace expira en 48 horas.</strong><br>
        Guarda el archivo en tu dispositivo para acceso permanente.
      </p>
    </div>
  </div>
  <p class="footer">Clínica Dr. Vega · Archivo compartido de forma segura</p>
</body>
</html>"""


@router.get("/s/{token}")
async def serve_share_link(token: str, request: Request, download: int = 0, raw: int = 0):
    """
    Servir archivo vía share token público (sin autenticación).
    - Sin parámetros: muestra página HTML con preview + botón de descarga
    - ?raw=1: sirve el archivo inline (para preview en la página HTML)
    - ?download=1: sirve el archivo como attachment (descarga directa)
    El token expira según configuración (default 48h).
    """
    record = file_service.get_file_by_token(token)
    if not record:
        # Página de error amigable
        return HTMLResponse(content="""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Enlace expirado</title>
<style>body{font-family:-apple-system,sans-serif;background:#f0f2f5;display:flex;align-items:center;
justify-content:center;min-height:100vh;padding:24px}
.card{background:white;border-radius:20px;padding:40px 32px;text-align:center;max-width:360px;
box-shadow:0 4px 24px rgba(0,0,0,.1)}
h1{font-size:1.2rem;color:#e74c3c;margin-top:16px}p{color:#888;margin-top:8px;font-size:.9rem}</style>
</head><body><div class="card">
<div style="font-size:3rem">⏰</div>
<h1>Enlace expirado o no disponible</h1>
<p>Este archivo ya no está disponible. El enlace tiene una duración de 48 horas.</p>
<p style="margin-top:16px;font-size:.8rem;color:#bbb">Si necesitas el archivo, solicítalo nuevamente.</p>
</div></body></html>""", status_code=404)

    full_path = get_file_path(record["file_path"])
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado en almacenamiento")

    file_size = os.path.getsize(full_path)

    # ?download=1 → descarga directa (attachment)
    if download:
        return StreamingResponse(
            _stream_file(full_path),
            media_type=record["content_type"],
            headers={
                "Content-Disposition": f'attachment; filename="{record["filename"]}"',
                "Cache-Control": "public, max-age=86400",
                "Content-Length": str(file_size),
            },
        )

    # ?raw=1 → inline para preview en la página HTML
    if raw:
        return StreamingResponse(
            _stream_file(full_path),
            media_type=record["content_type"],
            headers={
                "Content-Disposition": f'inline; filename="{record["filename"]}"',
                "Cache-Control": "public, max-age=86400",
                "Content-Length": str(file_size),
            },
        )

    # Sin parámetros → página HTML con preview + botón de descarga
    from app.config import settings
    base_url = settings.PUBLIC_URL.rstrip("/")
    html = _build_download_page(token, record, file_size, base_url)
    return HTMLResponse(content=html)



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

