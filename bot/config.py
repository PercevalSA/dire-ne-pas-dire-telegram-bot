from __future__ import annotations

import os
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path


@dataclass(frozen=True)
class Config:
    bot_token: str
    tz: str
    daily_time: str
    check_interval_min: int
    db_path: str


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    return int(raw)


def _default_db_path() -> str:
    """
    Prefer system-wide state directory on Linux.
    If not writable (e.g. running as an unprivileged user), fallback to user data dir.
    """
    system_path = Path("/var/lib/dire-ne-pas-dire-telegram-bot/bot.db")
    try:
        parent = system_path.parent
        if parent.exists() and os.access(parent, os.W_OK):
            return str(system_path)
        if parent.exists() is False and os.access("/var/lib", os.W_OK):
            return str(system_path)
    except Exception:
        pass

    xdg = os.getenv("XDG_DATA_HOME", "").strip()
    if xdg:
        return str(Path(xdg) / "dire-ne-pas-dire-telegram-bot" / "bot.db")
    return str(Path.home() / ".local" / "share" / "dire-ne-pas-dire-telegram-bot" / "bot.db")


def env_example_path(db_path: str) -> Path:
    parent = Path(db_path).expanduser().resolve().parent
    return parent / "dire-ne-pas-dire-telegram-bot.env.example"


def ensure_env_example(db_path: str) -> Path | None:
    """
    Write an env template next to the database if missing.
    Useful on servers where only the venv is deployed (pip install), not the repo.
    """
    try:
        p = env_example_path(db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            return p
        template = (
            files("bot")
            .joinpath("dire-ne-pas-dire-telegram-bot.env.example")
            .read_text(encoding="utf-8")
        )
        p.write_text(template.format(db_path=db_path), encoding="utf-8")
        return p
    except Exception:
        return None


def load_config() -> Config:
    db_path = os.getenv("DB_PATH", "").strip() or _default_db_path()
    ensure_env_example(db_path)

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("Missing BOT_TOKEN environment variable.")

    tz = os.getenv("TZ", "Europe/Paris").strip() or "Europe/Paris"
    daily_time = os.getenv("DAILY_TIME", "09:00").strip() or "09:00"
    check_interval_min = _get_int("CHECK_INTERVAL_MIN", 60)

    return Config(
        bot_token=bot_token,
        tz=tz,
        daily_time=daily_time,
        check_interval_min=check_interval_min,
        db_path=db_path,
    )
