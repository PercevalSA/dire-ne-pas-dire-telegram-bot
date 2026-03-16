from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from .config import hydrate_chat_id_from_db, load_config
from .db import init_db, set_meta
from .scheduler import send_next_unsent, start_scheduler


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
log = logging.getLogger("dire-ne-pas-dire-telegram-bot")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_chat
    application = context.application
    cfg = application.bot_data["cfg"]
    # Auto-enregistre le chat_id si absent (dans la base, pour les redémarrages).
    if cfg.chat_id is None and update.effective_chat:
        chat_id = update.effective_chat.id
        set_meta(cfg.db_path, "chat_id", str(chat_id))
        cfg = hydrate_chat_id_from_db(cfg)
        application.bot_data["cfg"] = cfg
        _start_scheduler_if_needed(application)

    await update.message.reply_text(
        "OK. Utilise /identifiant pour récupérer ton CHAT_ID.\n"
        "Utilise /prochain (ou /article) pour recevoir le prochain article non envoyé.",
    )


async def cmd_chatid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_chat
    await update.message.reply_text(f"CHAT_ID = {update.effective_chat.id}")


async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = context.application.bot_data["cfg"]
    chat_id = cfg.chat_id or (update.effective_chat.id if update.effective_chat else None)
    if chat_id is None:
        await update.message.reply_text("Impossible de déterminer le chat_id.")
        return
    ok = await send_next_unsent(context.application, cfg.db_path, chat_id)
    if not ok:
        await update.message.reply_text("Aucun nouvel article trouvé (tous déjà envoyés ?).")


async def post_init(application: Application) -> None:
    _start_scheduler_if_needed(application)


def _start_scheduler_if_needed(application: Application) -> None:
    # Démarre une seule fois (post_init ou après auto-enregistrement du chat_id).
    if application.bot_data.get("scheduler_started"):
        return
    cfg = application.bot_data["cfg"]
    if cfg.chat_id is None:
        log.warning("CHAT_ID absent: le scheduler ne démarrera pas tant qu’il n’est pas configuré.")
        return
    start_scheduler(
        application,
        db_path=cfg.db_path,
        chat_id=cfg.chat_id,
        tz=cfg.tz,
        daily_time=cfg.daily_time,
        check_interval_min=cfg.check_interval_min,
    )
    application.bot_data["scheduler_started"] = True


def build_app() -> Application:
    cfg = load_config()
    init_db(cfg.db_path)
    cfg = hydrate_chat_id_from_db(cfg)

    application = (
        Application.builder()
        .token(cfg.bot_token)
        .post_init(post_init)
        .build()
    )
    application.bot_data["cfg"] = cfg
    application.bot_data["scheduler_started"] = False

    # Commandes en français (avec alias anglais pour compatibilité éventuelle).
    application.add_handler(CommandHandler(["start", "demarrer"], cmd_start))
    application.add_handler(CommandHandler(["identifiant", "chatid"], cmd_chatid))
    application.add_handler(CommandHandler(["prochain", "article", "next"], cmd_next))

    return application


async def amain() -> None:
    app = build_app()
    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    log.info("Polling started.")
    await asyncio.Event().wait()


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()

