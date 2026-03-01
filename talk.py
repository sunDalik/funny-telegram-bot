import logging
import random
import re
from itertools import chain
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackContext, CommandHandler
import db
from db import M, MR
from utils import parse_userid, get_username_by_id, fmt_emoji_html, fmt_linked_msg_html, count_emojis
from _secrets import bot_talk

logger = logging.getLogger(__name__)
again_setter = None


async def _talk_simple(update: Update, context: CallbackContext, previous_results: list, from_user_id=None):
    if from_user_id is not None and int(from_user_id) == context.bot.id:
        texts = [(None, t) for t in bot_talk if t.lower() not in previous_results]
        result = random.choice(texts) if texts else None
    elif from_user_id is not None:
        result = next((
            (r[M.MSG_ID], r[M.TEXT])
            for r in db.get().execute(f"""SELECT {M.MSG_ID}, {M.TEXT} FROM {M.TABLE}
                                          WHERE {M.USER_ID} = ? ORDER BY RANDOM()""",
                                      (from_user_id,))
            if r[M.TEXT].lower() not in previous_results), None)
    else:
        row = db.get().execute(f"""SELECT {M.MSG_ID}, {M.TEXT} FROM {M.TABLE}
                                   ORDER BY RANDOM() LIMIT 1""").fetchone()
        result = (row[M.MSG_ID], row[M.TEXT]) if row else None

    if result is None:
        if previous_results:
            await update.message.reply_text("...", do_quote=False)
        elif from_user_id is not None:
            await update.message.reply_text(f"Кажется {get_username_by_id(from_user_id)} никогда ничего не говорил", do_quote=False)
        else:
            await update.message.reply_text("Кажется никто никогда ничего не говорил", do_quote=False)
    else:
        msg_id, text = result
        logger.info(f"  Result: {result}")
        if again_setter and from_user_id is not None:
            again_setter(lambda: _talk_simple(update, context, previous_results + [text.lower()], from_user_id))
        if msg_id is not None:
            await update.message.reply_text(fmt_linked_msg_html(text, msg_id, update.message.chat_id), do_quote=False, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(text, do_quote=False)


async def _talk_reactions(update: Update, context: CallbackContext, emoji_str: str, previous_results: list[int], from_user_id=None):
    emoji_params = count_emojis(emoji_str)
    if from_user_id is not None:
        subqueries = [
            f"SELECT {MR.TABLE}.{MR.MSG_ID} FROM {MR.TABLE}"
            f" JOIN {M.TABLE} ON {M.TABLE}.{M.MSG_ID} = {MR.TABLE}.{MR.MSG_ID}"
            f" WHERE {M.TABLE}.{M.USER_ID} = ? AND {MR.TABLE}.{MR.EMOJI} = ?"
            f" GROUP BY {MR.TABLE}.{MR.MSG_ID} HAVING COUNT(*) >= ?"
            for _ in emoji_params
        ]
        params = tuple(chain(*([from_user_id, e, c] for e, c in emoji_params)))
    else:
        subqueries = [
            f"SELECT {MR.MSG_ID} FROM {MR.TABLE}"
            f" WHERE {MR.EMOJI} = ?"
            f" GROUP BY {MR.MSG_ID} HAVING COUNT(*) >= ?"
            for _ in emoji_params
        ]
        params = tuple(chain(*emoji_params))

    rows = db.get().execute(" INTERSECT ".join(subqueries), params)
    if candidate_msg_ids := {int(row[MR.MSG_ID]) for row in rows} - set(previous_results):
        msg_id = random.choice(list(candidate_msg_ids))
        if row := db.get().execute(f"SELECT {M.TEXT} FROM {M.TABLE} WHERE {M.MSG_ID} = ?", (msg_id,)).fetchone():
            if again_setter:
                again_setter(lambda: _talk_reactions(update, context, emoji_str, previous_results + [msg_id], from_user_id))
            await update.message.reply_text(fmt_linked_msg_html(row[M.TEXT], msg_id, update.message.chat_id), do_quote=False, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("О нет, я все забыл...", do_quote=False)
    else:
        emoji_display = (("комбо из " if sum(c for _, c in emoji_params) > 1 else "") +
                         "".join(fmt_emoji_html(e) * c for e, c in emoji_params))
        if previous_results and from_user_id is not None:
            await update.message.reply_text(f"Я уже показал все сообщения от {get_username_by_id(from_user_id)}, налутавшие {emoji_display}", do_quote=False, parse_mode=ParseMode.HTML)
        elif previous_results:
            await update.message.reply_text(f"Я уже показал все сообщения, налутавшие {emoji_display}", do_quote=False, parse_mode=ParseMode.HTML)
        elif from_user_id is not None:
            await update.message.reply_text(f"Да {get_username_by_id(from_user_id)} о {emoji_display} только мечтать может", do_quote=False, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(f"Не знаю никого, кто нафармил бы {emoji_display} одним сообщением", do_quote=False, parse_mode=ParseMode.HTML)


async def handle_talk(update: Update, context: CallbackContext):
    logger.info(f"[talk] {update.message.text_html}")
    if emoji_match := re.match(r'/[\S]+\s+(.+)', update.message.text_html):
        await _talk_reactions(update, context, emoji_match.group(1).strip(), [], None)
    else:
        await _talk_simple(update, context, [], None)


async def handle_talklike(update: Update, context: CallbackContext):
    logger.info(f"[talklike] {update.message.text_html}")
    if match := re.match(r'/[\S]+\s+([\S]+)(?:\s+(.+))?', update.message.text_html):
        name = match.group(1)
        if user_id := parse_userid(name, context):
            if match.group(2):
                await _talk_reactions(update, context, match.group(2), [], user_id)
            else:
                await _talk_simple(update, context, [], user_id)
        else:
            await update.message.reply_text(f'"{name}"? В наших краях таких не знают', do_quote=True)
    else:
        await update.message.reply_text("Смотри, сначала пишешь имя человека, потом через пробел можешь добавить реакты. Несложно же?", do_quote=True)


def subscribe(a: Application, _again_setter):
    a.add_handler(CommandHandler(("talk", "t"), handle_talk))
    a.add_handler(CommandHandler(("talklike", "tl"), handle_talklike))
    global again_setter
    again_setter = _again_setter
