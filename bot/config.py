from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    bot_token: str
    chat_id: int | None
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
    system_path = Path("/var/lib/academie-fr-dnpd-tgbot/bot.db")
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
        return str(Path(xdg) / "academie-fr-dnpd-tgbot" / "bot.db")
    return str(Path.home() / ".local" / "share" / "academie-fr-dnpd-tgbot" / "bot.db")


def load_config() -> Config:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("Missing BOT_TOKEN environment variable.")

    chat_id_raw = os.getenv("CHAT_ID", "").strip()
    chat_id = int(chat_id_raw) if chat_id_raw else None

    tz = os.getenv("TZ", "Europe/Paris").strip() or "Europe/Paris"
    daily_time = os.getenv("DAILY_TIME", "09:00").strip() or "09:00"
    check_interval_min = _get_int("CHECK_INTERVAL_MIN", 60)
    db_path = os.getenv("DB_PATH", "").strip() or _default_db_path()

    return Config(
        bot_token=bot_token,
        chat_id=chat_id,
        tz=tz,
        daily_time=daily_time,
        check_interval_min=check_interval_min,
        db_path=db_path,
    )
