from _secrets import user_aliases, lucky_numbers
from telegram.ext import CallbackContext
from collections import Counter
import random
import db
from db import U
import re
import regex

# Don't include apostrophe
PUNCTUATION_REGEX = re.compile(r'[\s{}]+'.format(re.escape(r'!"#$%&()*+, -./:;<=>?@[\]^_`{|}~')))


def fmt_number(n: int, suffix: str = "") -> str:
    return f"{n}{suffix} {lucky_numbers[n]}" if n in lucky_numbers else f"{n}{suffix}"


def fmt_emoji_html(emoji: str) -> str:
    if emoji.isdigit():  # custom emojis
        return f'<tg-emoji emoji-id="{emoji}">❓</tg-emoji>'
    return emoji


# Count repeated emojis as well as emojis followed by a multiplier
# Example: given "😁😈2" or "😁😈😈", the result is [('😁', 1), ('😈', 2)]
def count_emojis(emoji_str: str) -> list[tuple[str, int]]:
    result = Counter()
    for m in regex.finditer(
        r'(?:<tg-emoji emoji-id="(\d+)">.*?</tg-emoji>|((?!\d|\s)\X))(\d*)',
        emoji_str,
    ):
        result[m[1] or m[2]] += int(m[3] or 1)
    return list(result.items())


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
