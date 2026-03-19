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


@dataclass(frozen=True)
class User:
    user_id: int
    chat_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    created_at: str
    updated_at: str


def ensure_parent_dir(db_path: str) -> None:
    parent = os.path.dirname(os.path.abspath(db_path))
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)


def init_db(db_path: str) -> None:
    ensure_parent_dir(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
              user_id INTEGER PRIMARY KEY,
              chat_id INTEGER NOT NULL UNIQUE,
              username TEXT,
              first_name TEXT,
              last_name TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_sent_articles (
              user_id INTEGER NOT NULL,
              url TEXT NOT NULL,
              title TEXT NOT NULL,
              sent_at TEXT NOT NULL,
              PRIMARY KEY (user_id, url),
              FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            """
        )
        _migrate_legacy_single_user_data(conn)
        conn.commit()


def _migrate_legacy_single_user_data(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", ("chat_id",)).fetchone()
    if row is None:
        return

    try:
        chat_id = int((row[0] or "").strip())
    except (TypeError, ValueError):
        conn.execute("DELETE FROM meta WHERE key = ?", ("chat_id",))
        return

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT OR IGNORE INTO users(user_id, chat_id, username, first_name, last_name, created_at, updated_at)
        VALUES (?, ?, NULL, NULL, NULL, ?, ?)
        """,
        (chat_id, chat_id, now, now),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO user_sent_articles(user_id, url, title, sent_at)
        SELECT ?, url, title, sent_at FROM sent_articles
        """,
        (chat_id,),
    )
    conn.execute("DELETE FROM meta WHERE key = ?", ("chat_id",))


@contextmanager
def db_conn(db_path: str):
    ensure_parent_dir(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
    finally:
        conn.close()


def has_sent(db_path: str, user_id: int, url: str) -> bool:
    with db_conn(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM user_sent_articles WHERE user_id = ? AND url = ?",
            (user_id, url),
        ).fetchone()
        return row is not None


def mark_sent(db_path: str, user_id: int, url: str, title: str) -> None:
    sent_at = datetime.now(timezone.utc).isoformat()
    with db_conn(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO user_sent_articles(user_id, url, title, sent_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, url, title, sent_at),
        )
        conn.commit()


def upsert_user(
    db_path: str,
    *,
    user_id: int,
    chat_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with db_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO users(user_id, chat_id, username, first_name, last_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
              chat_id = excluded.chat_id,
              username = excluded.username,
              first_name = excluded.first_name,
              last_name = excluded.last_name,
              updated_at = excluded.updated_at
            """,
            (user_id, chat_id, username, first_name, last_name, now, now),
        )
        conn.commit()


def delete_user(db_path: str, user_id: int) -> None:
    with db_conn(db_path) as conn:
        conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()


def list_users(db_path: str) -> list[User]:
    with db_conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT user_id, chat_id, username, first_name, last_name, created_at, updated_at
            FROM users
            ORDER BY created_at ASC
            """
        ).fetchall()
        return [User(*row) for row in rows]


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
