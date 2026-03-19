from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from telegram.error import Forbidden
from telegram.constants import ParseMode
from telegram.ext import Application

from .db import delete_user, has_sent, list_users, mark_sent
from .scrape import fetch_article_content, fetch_latest_articles, format_article_html, split_telegram_text

log = logging.getLogger(__name__)


async def _send_article(application: Application, *, chat_id: int, html: str) -> None:
    for chunk in split_telegram_text(html):
        await application.bot.send_message(
            chat_id=chat_id,
            text=chunk,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )


async def send_next_unsent(application: Application, db_path: str, user_id: int, chat_id: int) -> bool:
    articles = fetch_latest_articles(limit=60)
    for a in articles:
        if not has_sent(db_path, user_id, a.url):
            content = fetch_article_content(a)
            html = format_article_html(content)
            await _send_article(application, chat_id=chat_id, html=html)
            mark_sent(db_path, user_id, a.url, a.title)
            return True
    return False


async def send_if_new_latest(application: Application, db_path: str, user_id: int, chat_id: int) -> bool:
    articles = fetch_latest_articles(limit=10)
    if not articles:
        return False
    latest = articles[0]
    if has_sent(db_path, user_id, latest.url):
        return False
    content = fetch_article_content(latest)
    html = format_article_html(content)
    await _send_article(application, chat_id=chat_id, html=html)
    mark_sent(db_path, user_id, latest.url, latest.title)
    return True


async def _send_to_all_users(db_path: str, send_one) -> int:
    delivered = 0
    for user in list_users(db_path):
        try:
            delivered += int(await send_one(user.user_id, user.chat_id))
        except Forbidden:
            log.info("Removing user %s after Telegram reported the bot is blocked or unavailable.", user.user_id)
            delete_user(db_path, user.user_id)
        except Exception:
            log.exception("Failed to send article to user %s", user.user_id)
    return delivered


def start_scheduler(
    application: Application,
    *,
    db_path: str,
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
            delivered = await _send_to_all_users(
                db_path,
                lambda user_id, chat_id: send_next_unsent(application, db_path, user_id, chat_id),
            )
            if delivered == 0:
                log.warning("No unsent article found for daily job.")
        except Exception:
            log.exception("Daily job failed at %s", datetime.now())

    async def new_article_job() -> None:
        try:
            await _send_to_all_users(
                db_path,
                lambda user_id, chat_id: send_if_new_latest(application, db_path, user_id, chat_id),
            )
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

