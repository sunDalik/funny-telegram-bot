from _secrets import secrets_chat_ids
from telegram import Update
import logging

logger = logging.getLogger(__name__)


def in_whitelist(update: Update, send_warning=True) -> bool:
    if (update.message.chat_id not in secrets_chat_ids):
        logger.warn(f"Blacklisted chat id: {update.message.chat_id}")
        if send_warning:
             update.message.reply_text("This chat is not whitelisted")
        return False
    return True


USER_ID_TO_NAME = 'users'
