from _secrets import user_aliases, lucky_numbers, secrets_chat_ids
from telegram import Bot
from telegram.ext import CallbackContext
from telegram.error import TelegramError
from collections import Counter
import random
import db
from db import M, MR, U
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


async def fill_usernames(bot: Bot) -> tuple[int, int]:
    missing_user_ids = [r[0] for r in db.get().execute(f"""
        SELECT id FROM (
            SELECT {M.TABLE}.{M.USER_ID} AS id FROM {M.TABLE}
            UNION
            SELECT {MR.TABLE}.{MR.USER_ID} AS id FROM {MR.TABLE}
        ) WHERE id NOT IN (SELECT {U.USER_ID} FROM {U.TABLE})
    """)]
    filled = 0
    for user_id in missing_user_ids:
        for chat_id in secrets_chat_ids:
            try:
                member = await bot.get_chat_member(chat_id, user_id)
                username = member.user.username or member.user.first_name
                if username:
                    db.get().insert(db.User(user_id=user_id, username=username))
                    filled += 1
                    break
            except TelegramError:
                continue
    if filled:
        db.get().commit()
    return (len(missing_user_ids), filled)


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
