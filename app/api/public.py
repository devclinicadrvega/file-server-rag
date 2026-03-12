import os
import logging
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse, HTMLResponse
from app.services import file_service
from app.services.storage_service import get_file_path
from app.auth import require_api_key
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


def _stream_file(full_path: str, chunk_size: int = 65536):
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


def _type_info(content_type: str):
    if content_type.startswith("image/"):
        return "imagen", "Imagen"
    if content_type.startswith("video/"):
        return "video", "Video"
    if content_type.startswith("audio/"):
        return "audio", "Audio"
    return "documento", "Documento"


ICONS = {"imagen": "image_icon", "video": "video_icon", "audio": "audio_icon", "documento": "doc_icon"}


def _build_page(token: str, record: dict, file_size: int) -> str:
    filename = record["filename"]
    content_type = record["content_type"]
    size_str = _format_size(file_size)
    type_key, type_label = _type_info(content_type)
    download_url = f"{settings.PUBLIC_URL.rstrip('/')}/s/{token}?download=1"

    emoji_map = {"imagen": "image_e", "video": "video_e", "audio": "audio_e", "documento": "doc_e"}

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{type_label} - Clinica Dr. Vega</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
      background:#f0f2f5;min-height:100vh;display:flex;flex-direction:column;
      align-items:center;justify-content:center;padding:24px 16px}}
    .card{{background:#fff;border-radius:20px;box-shadow:0 4px 24px rgba(0,0,0,.10);
      max-width:400px;width:100%;padding:36px 28px;text-align:center}}
    .icon{{font-size:4rem;margin-bottom:12px}}
    h1{{font-size:1rem;font-weight:600;color:#222;word-break:break-word;margin-bottom:4px}}
    .meta{{font-size:.82rem;color:#888;margin-bottom:28px}}
    .btn{{display:block;width:100%;padding:18px;border-radius:12px;font-size:1.1rem;
      font-weight:700;text-decoration:none;color:#fff;margin-bottom:12px;
      background:linear-gradient(135deg,#25D366 0%,#128C7E 100%);
      box-shadow:0 4px 14px rgba(37,211,102,.35)}}
    .btn:active{{opacity:.88}}
    .note{{font-size:.78rem;color:#e67e22;margin-top:16px;line-height:1.6}}
    #inapp-banner{{display:none;background:#fff3cd;border:1px solid #ffc107;
      border-radius:12px;padding:16px;margin-bottom:20px;text-align:left}}
    #inapp-banner p{{font-size:.85rem;color:#856404;line-height:1.6}}
    #inapp-banner strong{{display:block;margin-bottom:6px;font-size:.9rem}}
    .copy-btn{{display:block;width:100%;margin-top:10px;padding:10px 16px;
      background:#ffc107;color:#000;border-radius:8px;font-size:.85rem;
      font-weight:700;cursor:pointer;border:none}}
    .footer{{font-size:.7rem;color:#bbb;margin-top:20px;text-align:center}}
  </style>
</head>
<body>
  <div class="card">
    <div id="inapp-banner">
      <p>
        <strong>&#9888;&#65039; Navegador interno detectado</strong>
        Para descargar el archivo abre este enlace en Chrome o Safari:<br>
        1. Toca el boton de abajo para copiar el enlace<br>
        2. Pegalo en Chrome o Safari y descarga ahi
      </p>
      <button class="copy-btn" onclick="copyLink()">&#128203; Copiar enlace de descarga</button>
    </div>

    <div id="icon-img"  class="icon" style="display:none">&#128444;&#65039;</div>
    <div id="icon-video" class="icon" style="display:none">&#127909;</div>
    <div id="icon-audio" class="icon" style="display:none">&#127925;</div>
    <div id="icon-doc"  class="icon" style="display:none">&#128196;</div>

    <h1>{filename}</h1>
    <p class="meta">{type_label} &middot; {size_str} &middot; valido 48h</p>

    <a id="dl-btn" href="{download_url}" class="btn">&#11015;&#65039;&nbsp; Descargar {type_label}</a>
    <p class="note">&#9888;&#65039; Este enlace expira en 48 horas.<br>Guarda el archivo en tu dispositivo para acceso permanente.</p>
  </div>
  <p class="footer">Clinica Dr. Vega &middot; Archivo compartido de forma segura</p>

  <script>
    var dlUrl = "{download_url}";
    var typeKey = "{type_key}";
    var iconMap = {{imagen:"icon-img", video:"icon-video", audio:"icon-audio", documento:"icon-doc"}};
    var el = document.getElementById(iconMap[typeKey] || "icon-doc");
    if (el) el.style.display = "block";

    var ua = navigator.userAgent;
    var isInApp = /FBAN|FBAV|Instagram|FB_IAB|Line|Twitter|Snapchat/i.test(ua);
    var isAndroid = /Android/i.test(ua);

    if (isInApp) {{
      document.getElementById("inapp-banner").style.display = "block";
      if (isAndroid) {{
        var intentUrl = "intent://" + dlUrl.replace(/^https?:\\/\\//, "") +
          "#Intent;scheme=https;package=com.android.chrome;end";
        document.getElementById("dl-btn").href = intentUrl;
      }}
    }} else {{
      // Navegador real: iniciar descarga automaticamente
      window.addEventListener("load", function() {{
        setTimeout(function() {{
          var a = document.createElement("a");
          a.href = dlUrl;
          a.download = "";
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
        }}, 600);
      }});
    }}

    function copyLink() {{
      var btn = document.querySelector(".copy-btn");
      if (navigator.clipboard) {{
        navigator.clipboard.writeText(dlUrl).then(function() {{
          btn.textContent = "Enlace copiado!";
        }});
      }} else {{
        var ta = document.createElement("textarea");
        ta.value = dlUrl;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
        btn.textContent = "Enlace copiado!";
      }}
    }}
  </script>
</body>
</html>"""


@router.get("/s/{token}")
async def serve_share_link(token: str, request: Request, download: int = 0):
    """
    Share link publico (sin autenticacion).
    - Sin parametros: pagina HTML con deteccion de in-app browser + descarga automatica en navegador real
    - ?download=1: sirve el archivo directamente como attachment (descarga forzada)
    """
    record = file_service.get_file_by_token(token)
    if not record:
        return HTMLResponse(content="""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Enlace expirado</title>
<style>body{font-family:-apple-system,sans-serif;background:#f0f2f5;display:flex;align-items:center;
justify-content:center;min-height:100vh;padding:24px}
.card{background:white;border-radius:20px;padding:40px 28px;text-align:center;max-width:360px;
box-shadow:0 4px 24px rgba(0,0,0,.1)}h1{font-size:1.1rem;color:#e74c3c;margin-top:12px}
p{color:#888;margin-top:8px;font-size:.85rem;line-height:1.5}</style>
</head><body><div class="card">
<div style="font-size:3rem">&#9200;</div>
<h1>Enlace expirado</h1>
<p>Este archivo ya no esta disponible.<br>Los enlaces tienen una duracion de 48 horas.</p>
<p style="margin-top:12px;font-size:.78rem;color:#bbb">Solicita el archivo nuevamente al equipo.</p>
</div></body></html>""", status_code=404)

    full_path = get_file_path(record["file_path"])
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado en almacenamiento")

    file_size = os.path.getsize(full_path)

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

    html = _build_page(token, record, file_size)
    return HTMLResponse(content=html)


@router.get("/f/{file_id}")
async def serve_internal_file(
    file_id: str,
    _: str = Depends(require_api_key),
):
    """Servir archivo por file_id (acceso interno autenticado con X-API-Key)."""
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
