import logging
import logging.handlers
from telegram import Update
from telegram.ext import Application, CallbackContext, CommandHandler
import re
import random
import db
from db import Message, M
from opinion import ENDINGS_REGEX
from utils import get_username_by_id, fmt_number
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

async def handle_chalice(update: Update, context: CallbackContext):
    logger.info(f"[chalice] {update.message.text}")
    match = re.match(r'/[\S]+\s+(.+)', update.message.text)
    if match is None:
        await update.message.reply_text("Какую чашу будем измерять?", do_quote=True)
        return
    user_input = match.group(1)
    await chalice(update, context, user_input)


async def chalice(update: Update, context: CallbackContext, user_input):
    days_limit = 14
    absolute_max = 56

    things = [thing for thing in re.split(r'\s+', user_input) if thing != ""]
    logger.info(f"  Parse result: {things}")
    chalice_title = things[0] if len(things) > 0 else ""
    things = [ENDINGS_REGEX.sub("", thing) for thing in things]

    total_messages = 0
    mention_messages = 0

    regexes = [re.compile(r'(?:[\s{}]+|^){}'.format(re.escape(r'!"#$%&()*+, -./:;<=>?@[\]^_`{|}~'), re.escape(thing)), flags=re.IGNORECASE) for thing in things]
    users = {}

    limit_ts = (datetime.now() - timedelta(days=days_limit)).timestamp()
    messages = db.get().fetch_many(Message, f"SELECT * FROM {M.TABLE} WHERE {M.TS} > ?", (limit_ts,))
    for message in messages:
        total_messages += 1
        if any(re.search(regex, message.text) for regex in regexes):
            mention_messages += 1
            if message.user_id not in users:
                users[message.user_id] = 1
            else:
                users[message.user_id] += 1

    ratio = mention_messages / absolute_max
    if mention_messages == 0:
        reply = random.choice([f"Чаша \"{chalice_title}\"... Абсолютно пуста!", f"В чаше \"{chalice_title}\" нет ни капельки!"])
        await update.message.reply_text(reply, do_quote=False)
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
            user_adj = random.choice(["ярый", "щедрый", "частый"])
            user_info = f"\n\nСамый {user_adj} наполнитель чаши — {get_username_by_id(sorted_users[0][0])} ({fmt_number(sorted_users[0][1], ' сообщ.')})"
            if ratio > 2:
                user_info = user_info.upper()
            reply += user_info

        await update.message.reply_text(reply, do_quote=False)


def subscribe(a: Application):
    a.add_handler(CommandHandler(("chalice", "cup", "c"), handle_chalice))
