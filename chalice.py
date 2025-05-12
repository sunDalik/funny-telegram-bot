import logging
import logging.handlers
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import re
import random
import redis_db
from opinion import ENDINGS_REGEX
from utils import in_whitelist, parse_userid
from datetime import date, datetime
from _secrets import lucky_numbers

r = redis_db.connect()
logger = logging.getLogger(__name__)

def handle_chalice(update: Update, context: CallbackContext):
    if (not in_whitelist(update)):
        return
    logger.info(f"[chalice] {update.message.text}")
    match = re.match(r'/[\S]+\s+(.+)', update.message.text)
    if match is None:
        update.message.reply_text("Какую чашу будем измерять?", quote=True)
        return
    user_input = match.group(1)
    chalice(update, context, user_input)


def chalice(update: Update, context, user_input):
    days_limit = 14
    absolute_max = 56

    things = [thing for thing in re.split(r'\s+', user_input) if thing != ""]
    logger.info(f"  Parse result: {things}")
    chalice_title = things[0] if len(things) > 0 else ""
    messages = redis_db.messages
    things = [ENDINGS_REGEX.sub("", thing) for thing in things]

    total_messages = 0
    mention_messages = 0

    regexes = [re.compile(r'(?:[\s{}]+|^){}'.format(re.escape(r'!"#$%&()*+, -./:;<=>?@[\]^_`{|}~'), re.escape(thing)), flags=re.IGNORECASE) for thing in things]
    now = datetime.now()
    users = {}

    for message in messages:
        message_date = datetime.fromtimestamp(message.ts) 
        if (now - message_date).days >= days_limit:
            continue

        total_messages += 1
        if any(re.search(regex, message.text) for regex in regexes):
            mention_messages += 1
            if message.uid not in users:
                users[message.uid] = 1
            else:
                users[message.uid] += 1

    ratio = mention_messages / absolute_max
    if mention_messages == 0:
        reply = random.choice([f"Чаша \"{chalice_title}\"... Абсолютно пуста!", f"В чаше \"{chalice_title}\" нет ни капельки!"])
        update.message.reply_text(reply, quote=False)
    else:
        formatted_ratio = f"{round(ratio * 100)}%"
        reply = f"Чаша \"{chalice_title}\" заполнена на {formatted_ratio}"
        reply += ".\n" if ratio <= 0.5 else "!\n"
        if ratio < 0.25:
            reply += random.choice([f"Как-то маловато... Поднажмем?", f"Как скудненько... А пить-то хочется!", f"Сушняк...", f"Подлейте добрые люди в чашу, кто сколько может..."])
        elif ratio < 0.5:
            reply += random.choice([f"Хорошая чаша, здоровая", f"Наливай еще, вся ночь только впереди!", f"Чаша начала заполняться... Но пока все только впереди!",  f"А ты наливай, наливай, не стесняйся!"])
        elif ratio < 0.75:
            reply += random.choice([f"Давай, давай еще по одной", f"Наливай, наливай, мы же миллионеры", f"Думаю можно еще подлить!",  f"А не рванет?... Не, наливаем еще!", f"Чаша заполняется..."])
        elif ratio < 1:
            reply += random.choice([f"Осторожнее, чаша в критическом состоянии...", f"Ой-ой-ой скоро перельется", f"Мужики, ну вам не хватит?", f"Ух как дискуссия-то разгорается... Ребята вы только осторожнее там"])
        elif ratio < 2:
            reply += random.choice([f"Ну вот, перелилась! Довольны?", f"Признавайтесь давайте, кто тут лужу наделал?!", f"Этому больше не наливайте!", f"Ну и кто вытирать это будет?!"])
        else:
            reply += random.choice([f"ПОТОООООООООООП", f"АТААААААААСССС", f"УЖАААААСССС", f"HHHHEEEEEELLPPP"])

        sorted_users = list(dict(sorted(users.items(), key=lambda item: item[1], reverse=True)).items())
        if ratio > 0.4 and (len(sorted_users) == 1 or (len(sorted_users) >= 2 and sorted_users[0][1] - sorted_users[1][1] >= 5)):
            lucky_char = lucky_numbers.get(sorted_users[0][1], '')
            if lucky_char != "":
                lucky_char = " " + lucky_char
            user_adj = random.choice(["ярый", "щедрый", "частый"])
            user_info = f"\n\nСамый {user_adj} наполнитель чаши — {redis_db.get_username_by_id(sorted_users[0][0])} ({sorted_users[0][1]} сообщ.{lucky_char})"
            if ratio > 2:
                user_info = user_info.upper()
            reply += user_info

        update.message.reply_text(reply, quote=False)


def subscribe(u: Updater):
    u.dispatcher.add_handler(CommandHandler(("chalice", "cup", "c"), handle_chalice))
