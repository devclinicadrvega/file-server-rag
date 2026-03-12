# File Server

Microservicio dedicado para almacenamiento y compartición de archivos del sistema Chat RAG.

**URL:** `https://files.crm.clinicadrvega.com`

## Responsabilidades
- Recibir y almacenar archivos en S3 (Coolify S3)
- Generar share links temporales (48h) para compartir con Facebook/Instagram/WhatsApp
- Servir archivos públicamente via token
- Servir archivos internamente via API key

## Endpoints

### Públicos (sin autenticación)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/s/{token}` | Servir archivo vía share token (48h) |
| GET | `/health` | Health check |

### Internos (requieren `X-API-Key`)
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/upload` | Subir archivo |
| POST | `/api/share/{file_id}` | Crear nuevo share token |
| GET | `/api/info/{file_id}` | Info de archivo |
| GET | `/f/{file_id}` | Servir por ID |
| GET | `/api/presigned/{file_id}` | URL presignada S3 |
| DELETE | `/api/tokens/cleanup` | Limpiar tokens expirados |

## Variables de entorno

Ver `.env.example` para la lista completa.

### Cómo habilitar S3 en Coolify

1. En Coolify → **Settings** → **S3 Storage**
2. Click **Add S3 Storage**
3. Llenar endpoint, access key, secret key, bucket y region
4. Copiar los valores al `.env` del servicio

## Estructura

```
app/
├── main.py          # FastAPI app
├── config.py        # Settings
├── database.py      # SQLite
├── auth.py          # API key validation
├── api/
│   ├── public.py    # /s/{token}, /f/{file_id}
│   └── internal.py  # /api/upload, /api/share, etc.
└── services/
    ├── s3_service.py
    └── file_service.py
```

## Integración con el backend principal

```env
FILE_SERVER_URL=https://files.crm.clinicadrvega.com
FILE_SERVER_API_KEY=<mismo valor que API_KEY en file-server>
```