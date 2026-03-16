from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from telegram.constants import ParseMode
from telegram.ext import Application

from .db import has_sent, mark_sent
from .scrape import fetch_latest_articles, format_message

log = logging.getLogger(__name__)


async def send_next_unsent(application: Application, db_path: str, chat_id: int) -> bool:
    articles = fetch_latest_articles(limit=60)
    for a in articles:
        if not has_sent(db_path, a.url):
            await application.bot.send_message(
                chat_id=chat_id,
                text=format_message(a),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=False,
            )
            mark_sent(db_path, a.url, a.title)
            return True
    return False


async def send_if_new_latest(application: Application, db_path: str, chat_id: int) -> bool:
    articles = fetch_latest_articles(limit=10)
    if not articles:
        return False
    latest = articles[0]
    if has_sent(db_path, latest.url):
        return False
    await application.bot.send_message(
        chat_id=chat_id,
        text=format_message(latest),
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=False,
    )
    mark_sent(db_path, latest.url, latest.title)
    return True


def start_scheduler(
    application: Application,
    *,
    db_path: str,
    chat_id: int,
    tz: str,
    daily_time: str,
    check_interval_min: int,
) -> AsyncIOScheduler:
    hh, mm = daily_time.split(":", 1)
    hour = int(hh)
    minute = int(mm)

    scheduler = AsyncIOScheduler(timezone=tz)

    async def daily_job() -> None:
        try:
            ok = await send_next_unsent(application, db_path, chat_id)
            if not ok:
                log.warning("No unsent article found for daily job.")
        except Exception:
            log.exception("Daily job failed at %s", datetime.now())

    async def new_article_job() -> None:
        try:
            await send_if_new_latest(application, db_path, chat_id)
        except Exception:
            log.exception("New-article job failed at %s", datetime.now())

    scheduler.add_job(
        daily_job,
        trigger=CronTrigger(hour=hour, minute=minute),
        id="daily_send",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )

    scheduler.add_job(
        new_article_job,
        trigger=IntervalTrigger(minutes=check_interval_min),
        id="check_new_article",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )

    scheduler.start()
    return scheduler

