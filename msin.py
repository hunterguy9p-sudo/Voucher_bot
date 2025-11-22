# main.py

import logging
from telegram.ext import ApplicationBuilder

from config import BOT_TOKEN
from user_panel import get_user_handlers
from admin_panel import get_admin_handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # register user handlers
    for h in get_user_handlers():
        app.add_handler(h)

    # register admin handlers
    for h in get_admin_handlers():
        app.add_handler(h)

    logger.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
