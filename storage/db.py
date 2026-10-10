"""SQLite storage: sent-mail log (for follow-ups) and reusable templates."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from config import settings

DB_PATH = settings.DB_PATH


@contextmanager
def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sent_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sent_at TEXT NOT NULL,
                to_addr TEXT,
                subject TEXT,
                message_id TEXT,
                thread_id TEXT,
                replied INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS templates (
                name TEXT PRIMARY KEY,
                subject TEXT,
                body TEXT
            );
            """
        )


def log_sent(
    to: str,
    subject: str,
    message_id: str | None,
    thread_id: str | None,
    sent_at: str | None = None,
) -> int:
    sent_at = sent_at or datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO sent_log (sent_at, to_addr, subject, message_id, thread_id) VALUES (?,?,?,?,?)",
            (sent_at, to, subject, message_id, thread_id),
        )
        return cur.lastrowid


def recent_sent(limit: int = 10) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM sent_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def pending_follow_ups(days: int = 5) -> list[dict]:
    """Sent mails older than `days` that are not yet marked as replied."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM sent_log WHERE replied = 0 AND sent_at <= ? ORDER BY sent_at",
            (cutoff,),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_replied(row_id: int) -> None:
    with _connect() as conn:
        conn.execute("UPDATE sent_log SET replied = 1 WHERE id = ?", (row_id,))


def save_template(name: str, subject: str, body: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO templates (name, subject, body) VALUES (?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET subject=excluded.subject, body=excluded.body",
            (name, subject, body),
        )


def get_template(name: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM templates WHERE name = ?", (name,)).fetchone()
    return dict(row) if row else None


def list_templates() -> list[str]:
    with _connect() as conn:
        rows = conn.execute("SELECT name FROM templates ORDER BY name").fetchall()
    return [r["name"] for r in rows]
