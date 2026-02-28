from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackContext, CommandHandler
import db
from db import M, MR
from utils import get_username_by_id, fmt_emoji_html, parse_userid
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta
import random
from _secrets import glaze_verbs

logger = logging.getLogger(__name__)


# glazer -> glazee -> emoji -> count
def _count_glaze() -> defaultdict[int, defaultdict[int, defaultdict[str, int]]]:
    days_limit = 14
    limit_ts = (datetime.now() - timedelta(days=days_limit)).timestamp()
    counts = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for row in db.get().execute(f"""
        SELECT {M.TABLE}.{M.USER_ID} as glazee_id,
               {MR.TABLE}.{MR.USER_ID} as glazer_id,
               {MR.TABLE}.{MR.EMOJI}, COUNT(*) as cnt
        FROM {MR.TABLE}
        JOIN {M.TABLE} ON {MR.TABLE}.{MR.MSG_ID} = {M.TABLE}.{M.MSG_ID}
        WHERE {MR.TABLE}.{MR.TS} > ? AND {MR.TABLE}.{MR.USER_ID} != {M.TABLE}.{M.USER_ID}
        GROUP BY {MR.TABLE}.{MR.USER_ID}, {M.TABLE}.{M.USER_ID}, {MR.TABLE}.{MR.EMOJI}
        ORDER BY cnt DESC
    """, (limit_ts,)
    ):
        counts[row['glazer_id']][row['glazee_id']][row[MR.EMOJI]] += row['cnt']
    return counts


def _list_glaze(user_emoji_count: dict[int, defaultdict[str, int]], top_users_limit: int) -> list[str]:
    top_emojis_limit = 3

    list = []
    top_users = sorted(user_emoji_count.items(), key=lambda x: sum(x[1].values()), reverse=True)
    for user_id, emojis in top_users[:top_users_limit]:
        total = sum(emojis.values())
        ranked_emojis = [e for e, _ in sorted(emojis.items(), key=lambda x: x[1], reverse=True)]
        top_emoji_str = ''.join(fmt_emoji_html(e) for e in ranked_emojis[:top_emojis_limit])
        list.append(f"{get_username_by_id(user_id)} ({total}, чаще {top_emoji_str})")
    return list


async def _glazestats_global(update: Update):
    top_glazees_limit = 2

    counts = _count_glaze()
    top_glazers = sorted(counts, key=lambda gz: sum(sum(ge.values()) for ge in counts[gz].values()), reverse=True)
    message = f"Вот что я последнее время замечаю:\n"
    for i, glazer_id in enumerate(top_glazers, 1):
        message += f"{i}. {get_username_by_id(glazer_id)} {random.choice(glaze_verbs)[0]}:\n"
        message += ''.join(f"* {g}\n" for g in _list_glaze(counts[glazer_id], top_glazees_limit))

    await update.message.reply_text(message, do_quote=False, parse_mode=ParseMode.HTML)


async def _glazestats_user(update: Update, user_id: int):
    top_limit = 5

    counts = _count_glaze()
    glazing = counts[user_id]
    glazed_by = {glazer_id: glazees[user_id] for glazer_id, glazees in counts.items() if user_id in glazees}

    message = f"Последнее время, {get_username_by_id(user_id)} больше всего {random.choice(glaze_verbs)[0]}:\n"
    message += ''.join(f"{i}) {g}\n" for i, g in enumerate(_list_glaze(glazing, top_limit), 1))
    message += f"\nА {random.choice(glaze_verbs)[1]} {get_username_by_id(user_id)} в свою очередь больше всего:\n"
    message += ''.join(f"{i}) {g}\n" for i, g in enumerate(_list_glaze(glazed_by, top_limit), 1))

    await update.message.reply_text(message, do_quote=False, parse_mode=ParseMode.HTML)


async def glazestats(update: Update, context: CallbackContext):
    logger.info(f"[glazestats] {update.message.text}")
    if match := re.match(r'/[\S]+\s+([\S]+)', update.message.text):
        username = match.group(1)
        if user_id := parse_userid(username, context):
            await _glazestats_user(update, user_id)
        else:
            await update.message.reply_text(f'"{username}"? И кто это должен быть?', do_quote=True)
    else:
        await _glazestats_global(update)


def subscribe(a: Application):
    a.add_handler(CommandHandler("glazestats", glazestats))
