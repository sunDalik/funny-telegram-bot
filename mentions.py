from telegram import Update
from telegram.ext import Application, CallbackContext, CommandHandler
import db
from db import M
from utils import get_username_by_id, fmt_number
import logging
import re

logger = logging.getLogger(__name__)

async def mentions(update: Update, context: CallbackContext):
    logger.info(f"[mentions] {update.message.text}")
    match = re.match(r'/[\S]+\s+(.+)', update.message.text)
    if match == None:
        await update.message.reply_text("Упоминания чего будем считать?", do_quote=True)
        return
    user_input = match.group(1).strip()
    result = {}
    regex = re.compile(r'(?:[\s{}]+|^){}'.format(re.escape(r'!"#$%&()*+, -./:;<=>?@[\]^_`{|}~'), re.escape(user_input)), flags=re.IGNORECASE)
    for msg in db.get().execute(f"SELECT {M.USER_ID}, {M.TEXT} FROM {M.TABLE}"):
        #if user_input_lower in msg.text.lower(): # If you want to count 1 occurence per message only
        #count = msg.text.lower().count(user_input_lower)
        # Only count occurrences at the beggining of words
        count = len(re.findall(regex, msg[M.TEXT]))
        if count != 0:
            if msg[M.USER_ID] not in result:
                result[msg[M.USER_ID]] = count
            else:
                result[msg[M.USER_ID]] += count

    if len(result) == 0:
        await update.message.reply_text(f"Кажется никто никогда не говорил \"{user_input}\"...\nСтань первым!", do_quote=False)
        return

    message = f"Собрал статистику упоминаний {'фразы' if ' ' in user_input else 'слова'} \"{user_input}\":\n"
    i = 1
    for k, v in dict(sorted(result.items(), key=lambda item: item[1], reverse=True)).items():
        message += f"{i}. {get_username_by_id(k)} — {fmt_number(v)}\n"
        i += 1

    await update.message.reply_text(message, do_quote=False)


def subscribe(a: Application):
    a.add_handler(CommandHandler(("mentions", "m", "opinionstats", "os"), mentions))
