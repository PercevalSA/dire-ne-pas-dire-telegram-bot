from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class SentItem:
    url: str
    title: str
    sent_at: str


def ensure_parent_dir(db_path: str) -> None:
    parent = os.path.dirname(os.path.abspath(db_path))
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)


def init_db(db_path: str) -> None:
    ensure_parent_dir(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sent_articles (
              url TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              sent_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            )
            """
        )
        conn.commit()


@contextmanager
def db_conn(db_path: str):
    ensure_parent_dir(db_path)
    conn = sqlite3.connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def has_sent(db_path: str, url: str) -> bool:
    with db_conn(db_path) as conn:
        row = conn.execute("SELECT 1 FROM sent_articles WHERE url = ?", (url,)).fetchone()
        return row is not None


def mark_sent(db_path: str, url: str, title: str) -> None:
    sent_at = datetime.now(timezone.utc).isoformat()
    with db_conn(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sent_articles(url, title, sent_at) VALUES (?, ?, ?)",
            (url, title, sent_at),
        )
        conn.commit()


def get_last_sent_url(db_path: str) -> str | None:
    with db_conn(db_path) as conn:
        row = conn.execute(
            "SELECT url FROM sent_articles ORDER BY sent_at DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None


def set_meta(db_path: str, key: str, value: str) -> None:
    with db_conn(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            (key, value),
        )
        conn.commit()


def get_meta(db_path: str, key: str) -> str | None:
    with db_conn(db_path) as conn:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None
