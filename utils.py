from _secrets import secrets_chat_ids, user_aliases
from telegram import Update
from telegram.ext import CallbackContext
import logging
import random
import redis_db
import re

logger = logging.getLogger(__name__)

# Don't include apostrophe
PUNCTUATION_REGEX = re.compile(r'[\s{}]+'.format(re.escape(r'!"#$%&()*+, -./:;<=>?@[\]^_`{|}~')))

def in_whitelist(update: Update, send_warning=True) -> bool:
    if (update.message.chat_id not in secrets_chat_ids):
        logger.warn(f"Blacklisted chat id: {update.message.chat_id}")
        # Bots have a global limit of 30 messages per second
        # https://core.telegram.org/bots/faq#broadcasting-to-users
        # We don't want to enable ddos attacks for blacklisted chats so we dont message them anything
        if False and send_warning:
             update.message.reply_text("This chat is not whitelisted")
        return False
    return True


def parse_userid(username: str, context: CallbackContext):
    username = username.strip()
    shuffled_alias_keys = list(user_aliases.keys())
    random.shuffle(shuffled_alias_keys)
    for alias_key in shuffled_alias_keys:
        for alias in user_aliases[alias_key]:
            if (alias.lower() == username.lower()):
                return alias_key
    
    if(username == context.bot.username or username == f"@{context.bot.username}"):
        return context.bot.id

    return redis_db.reverse_lookup_id(username)


USER_ID_TO_NAME = 'users'
