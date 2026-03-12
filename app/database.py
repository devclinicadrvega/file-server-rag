import sqlite3
import os
from contextlib import contextmanager
from app.config import settings


def get_db_path() -> str:
    os.makedirs(os.path.dirname(settings.DB_PATH), exist_ok=True)
    return settings.DB_PATH


def init_db():
    """Crear tablas si no existen."""
    with sqlite3.connect(get_db_path()) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS file_records (
                id          TEXT PRIMARY KEY,
                s3_key      TEXT NOT NULL UNIQUE,
                filename    TEXT NOT NULL,
                content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
                size_bytes  INTEGER NOT NULL DEFAULT 0,
                platform    TEXT DEFAULT NULL,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS share_tokens (
                token       TEXT PRIMARY KEY,
                file_id     TEXT NOT NULL,
                expires_at  TEXT NOT NULL,
                download_count INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (file_id) REFERENCES file_records(id) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_share_tokens_file_id ON share_tokens(file_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_share_tokens_expires ON share_tokens(expires_at)")
        # Migración: agregar columna scheduled_delete_at si no existe
        try:
            conn.execute("ALTER TABLE file_records ADD COLUMN scheduled_delete_at TEXT DEFAULT NULL")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_file_records_delete ON file_records(scheduled_delete_at)")
        except Exception:
            pass  # La columna ya existe
        conn.commit()


@contextmanager
def get_db():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
