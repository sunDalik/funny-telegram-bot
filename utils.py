from _secrets import user_aliases
from telegram.ext import CallbackContext
import logging
import random
import db
from db import U
import re

logger = logging.getLogger(__name__)

# Don't include apostrophe
PUNCTUATION_REGEX = re.compile(r'[\s{}]+'.format(re.escape(r'!"#$%&()*+, -./:;<=>?@[\]^_`{|}~')))


def get_username_by_id(user_id: int) -> str:
    row = db.get().execute(f"SELECT {U.USERNAME} FROM {U.TABLE} WHERE {U.USER_ID}=?", (user_id,)).fetchone()
    return row[U.USERNAME] if row else str(user_id)


def parse_userid(username: str, context: CallbackContext) -> int | None:
    username = username.strip().lstrip('@')
    shuffled_alias_keys = list(user_aliases.keys())
    random.shuffle(shuffled_alias_keys)
    for alias_key in shuffled_alias_keys:
        for alias in user_aliases[alias_key]:
            if (alias.lower() == username.lower()):
                return alias_key

    if username == context.bot.username:
        return context.bot.id

    row = db.get().execute(f"SELECT {U.USER_ID} FROM {U.TABLE} WHERE LOWER({U.USERNAME}) = LOWER(?)", (username,)).fetchone()
    return int(row[U.USER_ID]) if row else None
