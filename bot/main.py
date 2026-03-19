from __future__ import annotations

import asyncio
import logging

from telegram import ChatMemberUpdated, Update
from telegram.ext import Application, ChatMemberHandler, CommandHandler, ContextTypes

from .config import load_config
from .db import delete_user, init_db, upsert_user
from .scheduler import send_next_unsent, start_scheduler


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
log = logging.getLogger("dire-ne-pas-dire-telegram-bot")

INACTIVE_CHAT_MEMBER_STATUSES = {"left", "kicked"}


def _register_effective_user(update: Update, db_path: str) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    if chat is None or user is None or chat.type != "private":
        return False

    upsert_user(
        db_path,
        user_id=user.id,
        chat_id=chat.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )
    return True


def _extract_was_active_is_active(chat_member_update: ChatMemberUpdated) -> tuple[bool, bool]:
    old_status = chat_member_update.old_chat_member.status
    new_status = chat_member_update.new_chat_member.status
    was_active = old_status not in INACTIVE_CHAT_MEMBER_STATUSES
    is_active = new_status not in INACTIVE_CHAT_MEMBER_STATUSES
    return was_active, is_active


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = context.application.bot_data["cfg"]
    _register_effective_user(update, cfg.db_path)
    if update.message is not None:
        await update.message.reply_text(
            "OK. Tu es inscrit pour les notifications.\n"
            "Utilise /prochain (ou /article) pour recevoir le prochain article non envoyé.",
        )


async def cmd_chatid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_chat
    await update.message.reply_text(f"USER_ID = {update.effective_chat.id}")


async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = context.application.bot_data["cfg"]
    if not _register_effective_user(update, cfg.db_path):
        if update.message is not None:
            await update.message.reply_text("Cette commande est disponible uniquement en message privé avec le bot.")
        return

    assert update.effective_chat
    assert update.effective_user
    ok = await send_next_unsent(
        context.application,
        cfg.db_path,
        update.effective_user.id,
        update.effective_chat.id,
    )
    if not ok:
        await update.message.reply_text("Aucun nouvel article trouvé (tous déjà envoyés ?).")


async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_member_update = update.my_chat_member
    if chat_member_update is None or chat_member_update.chat.type != "private":
        return

    was_active, is_active = _extract_was_active_is_active(chat_member_update)
    cfg = context.application.bot_data["cfg"]
    user = chat_member_update.from_user

    if is_active:
        await asyncio.to_thread(
            upsert_user,
            cfg.db_path,
            user_id=user.id,
            chat_id=chat_member_update.chat.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )
        if not was_active:
            log.info("Registered user %s after my_chat_member activation.", user.id)
        return

    if was_active and not is_active:
        await asyncio.to_thread(delete_user, cfg.db_path, user.id)
        log.info("Deleted user %s after my_chat_member deactivation.", user.id)


def _start_scheduler_if_needed(application: Application) -> None:
    if application.bot_data.get("scheduler_started"):
        return
    cfg = application.bot_data["cfg"]
    start_scheduler(
        application,
        db_path=cfg.db_path,
        tz=cfg.tz,
        daily_time=cfg.daily_time,
        check_interval_min=cfg.check_interval_min,
    )
    application.bot_data["scheduler_started"] = True


def build_app() -> Application:
    cfg = load_config()
    init_db(cfg.db_path)

    application = (
        Application.builder()
        .token(cfg.bot_token)
        .build()
    )
    application.bot_data["cfg"] = cfg
    application.bot_data["scheduler_started"] = False

    # Commandes en français (avec alias anglais pour compatibilité éventuelle).
    application.add_handler(CommandHandler(["start", "demarrer"], cmd_start))
    application.add_handler(CommandHandler(["identifiant", "chatid"], cmd_chatid))
    application.add_handler(CommandHandler(["prochain", "article", "next"], cmd_next))
    application.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))

    return application


async def amain() -> None:
    app = build_app()
    await app.initialize()
    await app.start()
    _start_scheduler_if_needed(app)
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    log.info("Polling started.")
    await asyncio.Event().wait()


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()

