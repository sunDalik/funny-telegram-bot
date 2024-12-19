from telegram import Update
from telegram.ext import Updater, CommandHandler
import redis_db
from utils import in_whitelist
import logging
from _secrets import lucky_numbers
import re

logger = logging.getLogger(__name__)
r = redis_db.connect()

def mentions(update: Update, context):
    if (not in_whitelist(update)):
        return
    logger.info(f"[mentions] {update.message.text}")
    match = re.match(r'/[\S]+\s+(.+)', update.message.text)
    if match == None:
        update.message.reply_text("Упоминания чего будем считать?", quote=True)
        return
    user_input = match.group(1).strip()
    all_messages = [m for m in redis_db.messages]
    result = {}
    for msg in all_messages:
        #if user_input_lower in msg.text.lower(): # If you want to count 1 occurence per message only
        #count = msg.text.lower().count(user_input_lower)
        # Only count occurrences at the beggining of words
        count = len(re.findall(r'(?:[\s{}]+|^){}'.format(re.escape(r'!"#$%&()*+, -./:;<=>?@[\]^_`{|}~'), re.escape(user_input)), msg.text, flags=re.IGNORECASE))
        if count != 0:
            if msg.uid not in result:
                result[msg.uid] = count
            else:
                result[msg.uid] += count
    
    if len(result) == 0:
        update.message.reply_text(f"Кажется никто никогда не говорил \"{user_input}\"...\nСтань первым!", quote=False)
        return

    message = f"Собрал статистику упоминаний {'фразы' if ' ' in user_input else 'слова'} \"{user_input}\":\n"
    i = 1
    for k, v in dict(sorted(result.items(), key=lambda item: item[1], reverse=True)).items():
        message += f"{i}. {redis_db.get_username_by_id(k)} — {v}  {lucky_numbers.get(v, '')}\n"
        i += 1

    update.message.reply_text(message, quote=False)


def subscribe(u: Updater):
    u.dispatcher.add_handler(CommandHandler(("mentions", "m", "opinionstats", "os"), mentions))