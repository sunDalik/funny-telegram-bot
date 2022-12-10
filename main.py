from datetime import datetime
from datetime import timedelta
from datetime import time

from _secrets import secrets_bot_token, secrets_chat_ids
import logging
from telegram import ParseMode, Update
from telegram.ext import Updater, CommandHandler, Filters, MessageHandler
import redis
import re
import json
import random
from string import punctuation
from time import sleep

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

DICTIONARY_HASH = 'dictionary'
JERKS_REG_SET = 'jerks_reg'
USER_ID_TO_NAME = 'users'
JERKS = 'jerks'
JERKS_META = 'jerks_meta'
RECEIVED_MESSAGES_LIST = 'received_messages_list'
MESSAGES = []
MAX_ITERS = 999_999
PUNCTUATION_REGEX = re.compile(r'[\s{}]+'.format(re.escape(punctuation)))
ENDINGS_REGEX = re.compile(r"(?:ах|а|ев|ей|е|ов|о|иях|ия|ие|ий|й|ь|ы|ии|и|ях|я|у|ых|их|s)$", re.IGNORECASE)

again_function = None


def in_whitelist(update: Update) -> bool:
    if (update.message.chat_id not in secrets_chat_ids):
        logger.warn(f"Blacklisted chat id: {update.message.chat_id}")
        update.message.reply_text("This chat is not whitelisted")
        return False
    return True


def ping(update: Update, context):
    update.message.reply_text("Понг!", quote=True)


def test(update: Update, context):
    update.message.reply_text("Looking cool joker!", quote=False)


def contribute(update: Update, context):
    update.message.reply_text("https://github.com/sunDalik/funny-telegram-bot", quote=False)


def getDict(update: Update, context):
    if (not in_whitelist(update)):
        return
    logger.info(f"[getDict] {update.message.text}")
    match = re.match(r'/[\S]+\s+([^\s]+)', update.message.text)
    if (match == None):
        update.message.reply_text("Ты чего хочешь-то?", quote=True)
        return
    key = match.group(1)
    val = r.hget(DICTIONARY_HASH, key)
    if (val == None):
        update.message.reply_text("Не помню такого", quote=True)
        return
    update.message.reply_text(f"{key}\n{val.decode('utf-8')}", quote=False)


def setDict(update: Update, context):
    if (not in_whitelist(update)):
        return
    logger.info(f"[setDict] {update.message.text}")
    match = re.match(r'/[\S]+\s+([\S]+)\s+(.+)', update.message.text, re.DOTALL)
    if (match == None):
        update.message.reply_text("Что-то я ничего не понял. Удали свой /set и напиши нормально", quote=True)
        return

    key = match.group(1)
    val = match.group(2)
    old_value = r.hget(DICTIONARY_HASH, key)
    r.hset(DICTIONARY_HASH, key, val)
    if (old_value != None):
        update.message.reply_text(f"Запомнил {key}! Раньше там было \"{old_value.decode('utf-8')}\"", quote=False)
    else:
        update.message.reply_text(f"Запомнил {key}!", quote=False)

def delDict(update: Update, context):
    if (not in_whitelist(update)):
        return
    logger.info(f"[delDict] {update.message.text}")
    match = re.match(r'/[\S]+\s+([\S]+)', update.message.text)
    if (match == None):
        update.message.reply_text("Не понял, а что удалить-то хочешь?")
        return
    key = match.group(1)
    val = r.hdel(DICTIONARY_HASH, key)
    if (val == 0):
        update.message.reply_text(f"Чего-чего? \"{key}\"? Я такого не знаю", quote=False)
    else:
        update.message.reply_text(f"Ок, я удалил ключ \"{key}\"", quote=False)


def sentence_matches_definition(definition: str, sentence: list) -> bool:
    if (len(sentence) != len(definition)):
        return False
    for i, word in enumerate(sentence):
        if (word[0].lower() != definition[i].lower()):
            return False
    return True


def explain(update: Update, context):
    if (not in_whitelist(update)):
        return
    logger.info(f"[explain] {update.message.text}")
    match = re.match(r'/[\S]+\s+([\S]+)', update.message.text)
    if (match == None):
        update.message.reply_text("Что тебе объяснить?", quote=True)
        return
    global again_function
    again_function = lambda: explain(update, context)
    definition = match.group(1)
    result = None
    shuffled_messages = MESSAGES.copy()
    random.shuffle(shuffled_messages)
    for rnd_message in shuffled_messages:
        words = [w for w in PUNCTUATION_REGEX.split(rnd_message) if w != ""]
        if (sentence_matches_definition(definition, words)):
            result = rnd_message
            break

    if (result == None):
        update.message.reply_text(f"Я не знаю что такое \"{definition}\" ._.", quote=False)
        return
    logger.info(f"  Result: {result}")
    update.message.reply_text(f"*{definition}*\n{result}", parse_mode=ParseMode.MARKDOWN, quote=False)


def talk(update: Update, context):
    if (not in_whitelist(update)):
         return
    logger.info("[talk]")
    rnd_message = random.choice(MESSAGES)
    logger.info(f"  Result: {rnd_message}")
    update.message.reply_text(rnd_message, quote=False)


def opinion(update: Update, context):
    if (not in_whitelist(update)):
         return
    logger.info(f"[opinion] {update.message.text}")
    match = re.match(r'/[\S]+\s+(.+)', update.message.text)
    if (match == None):
        update.message.reply_text("О чем ты хотел узнать мое мнение?", quote=True)
        return
    global again_function
    again_function = lambda: opinion(update, context)
    user_input = match.group(1)
    things = [thing for thing in re.split(r'\s', user_input) if thing != ""]
    things = [ENDINGS_REGEX.sub("", thing).lower() for thing in things]
    logger.info(f"  Parse result: {things}")
    shuffled_messages = MESSAGES.copy()
    random.shuffle(shuffled_messages)
    for rnd_message in shuffled_messages:
        lower_message = rnd_message.lower()
        if (all(thing in lower_message for thing in things)):
            update.message.reply_text(rnd_message, quote=False)
            return
    update.message.reply_text(f"Я ничего не знаю о \"{user_input}\" >_<", quote=False)


def getAll(update: Update, context):
    if (not in_whitelist(update)):
        return
    logger.info("[getAll]")
    match = re.match(r'/[\S]+\s+([^\s]+)', update.message.text)
    must_start_with = ""
    if match:
        must_start_with += match.group(1)
    keys = r.hgetall(DICTIONARY_HASH)
    keys_list = [key.decode('utf-8') for key in keys]
    if must_start_with != "":
        keys_list = [key for key in keys_list if key.lower().startswith(must_start_with.lower())]
    keys_list.sort()
    header = 'Так вот же все ГЕТЫ:\n\n' if must_start_with == "" else f'Вот все ГЕТЫ, начинающиеся с \"{must_start_with}\":\n\n'
    response = ", ".join(keys_list)
    update.message.reply_text(header + response, quote=False)


def jerk_reg(update: Update, context):
    if not in_whitelist(update):
        return
    # set user id to regs
    logger.info('[jerk_reg]')
    reg_user_id = update.message.from_user.id
    reg_user_name = update.message.from_user.username
    already_register = r.sismember(JERKS_REG_SET, reg_user_id)
    count = r.scard(JERKS_REG_SET)
    if already_register:
        # rewrite username
        old_username = r.hget(USER_ID_TO_NAME, reg_user_id).decode('utf-8')
        if old_username != reg_user_name:
            r.hset(USER_ID_TO_NAME, reg_user_id, reg_user_name)
            update.message.reply_text(f"@{reg_user_name}, поменял твой никнейм.", quote=False)  # change to something funnier
            return
        update.message.reply_text(f"@{reg_user_name}, ты уже участник этой клоунады", quote=False)
        return
    # set user id and username
    r.sadd(JERKS_REG_SET, reg_user_id)
    r.hset(USER_ID_TO_NAME, reg_user_id, reg_user_name)
    update.message.reply_text(f"@{reg_user_name}, теперь ты участвуешь в лотерее вместе с {count} придурками", quote=False)


def jerk_of_the_day(update: Update, context):
    if (not in_whitelist(update)):
        return
    logger.info('[jerk_of_the_day]')
    # r.hdel(JERKS_META, 'roll_time')

    last_roll = r.hget(JERKS_META, 'roll_time')

    datetime_format = '%Y-%m-%d %H:%M:%S'
    cur_datetime = datetime.now()
    cur_datetime_str = cur_datetime.strftime(datetime_format)

    if last_roll:
        last_roll_dt = datetime.strptime(last_roll.decode('utf-8'), datetime_format)
        is_same_day = cur_datetime.year == last_roll_dt.year and cur_datetime.month == last_roll_dt.month \
                      and cur_datetime.day == last_roll_dt.day
        if is_same_day:
            cur_jerk_id = r.hget(JERKS_META, 'last_jerk')
            cur_jerk_username = r.hget(USER_ID_TO_NAME, cur_jerk_id).decode('utf-8')
            tomorrow = cur_datetime + timedelta(days=1)
            time_to_next = datetime.combine(tomorrow, time.min) - cur_datetime
            time_to_next_h, time_to_next_m = time_to_next.seconds // 3600, (time_to_next.seconds // 60) % 60
            update.message.reply_text(f"Сегодняшний придурок дня: *{cur_jerk_username}*.\n"
                                      f"Следующий запуск будет доступен через: "
                                      f"{time_to_next_h} ч. и {time_to_next_m} м.",
                                      quote=False, parse_mode=ParseMode.MARKDOWN)
            return
    players = r.smembers(JERKS_REG_SET)
    pl = [player.decode('utf-8') for player in players]
    if (len(pl) == 0):
        update.message.reply_text("А че вы роллить собрались? Никто не зарегистрировался", quote=True)
    winner_id = random.choice(pl)
    winner_username = r.hget(USER_ID_TO_NAME, winner_id).decode('utf-8')
    r.hset(JERKS_META, 'last_jerk', winner_id)
    r.hset(JERKS_META, 'roll_time', cur_datetime_str)
    r.hincrby(JERKS, winner_id, 1)

    update.message.reply_text("Выбираю долбаеба на сегодня", quote=False)
    sleep(1)
    update.message.reply_text(f"А вот и придурок - @{winner_username}", quote=False)
    logger.info(f'  WINNER for {cur_datetime_str} is {winner_id}: {winner_username}')
    return


def get_jerk_stats(update: Update, context):
    jerks_dict = {}
    for key in r.hgetall(JERKS):
        winner_username = r.hget(USER_ID_TO_NAME, key).decode('utf-8')
        jerks_dict[winner_username] = r.hget(JERKS, key)
    message = "Вот статистика придурков:\n"
    i = 1
    for k, v in dict(sorted(jerks_dict.items(), key=lambda item: item[1], reverse=True)).items():
        message += f"{i}. {k} - {v.decode('utf-8')}"
        i += 1
    update.message.reply_text(f"{message}", quote=False)


def error(update: Update, context):
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def again(update: Update, context):
    if again_function:
        try:
            again_function()
        except:
            update.message.reply_text("А что /again? Кажется я все забыл...", quote=False)
    else:
        update.message.reply_text("А что /again? Кажется я все забыл...", quote=False)

def handle_normal_messages(update: Update, context):
    if (not in_whitelist(update)):
         return
    logger.info(f"[msg] {update.message.text}")
    r.rpush(RECEIVED_MESSAGES_LIST, update.message.text)
    MESSAGES.append(update.message.text)

if __name__ == '__main__':
    logger.info("Initializing Redis")
    r = redis.Redis(host='localhost', port=6379, db=1)

    logger.info("Parsing messages...")
    f = open('_secrets/messages.json')
    data = json.load(f)
    for message in data['messages']:
        if ("text_entities" in message):
            text = "".join([txt.get("text") for txt in message.get("text_entities")])
            if (text != ""):
                MESSAGES.append(text)
    f.close()

    for message in r.lrange(RECEIVED_MESSAGES_LIST, 0, -1):
        message = message.decode("utf-8")
        MESSAGES.append(message)

    logger.info("Setting up telegram bot")
    u = Updater(secrets_bot_token, use_context=True)

    u.dispatcher.add_handler(CommandHandler("ping", ping))
    u.dispatcher.add_handler(CommandHandler("get", getDict))
    u.dispatcher.add_handler(CommandHandler("set", setDict))
    u.dispatcher.add_handler(CommandHandler("explain", explain))
    u.dispatcher.add_handler(CommandHandler("talk", talk))
    u.dispatcher.add_handler(CommandHandler("opinion", opinion))
    u.dispatcher.add_handler(CommandHandler("contribute", contribute))
    u.dispatcher.add_handler(CommandHandler("getall", getAll))
    u.dispatcher.add_handler(CommandHandler("reg", jerk_reg))
    u.dispatcher.add_handler(CommandHandler("jerk", jerk_of_the_day))
    u.dispatcher.add_handler(CommandHandler("del", delDict))
    u.dispatcher.add_handler(CommandHandler("again", again))
    u.dispatcher.add_handler(CommandHandler("jerkstats", get_jerk_stats))

    u.dispatcher.add_handler(CommandHandler("test", lambda update, context: test(update, context)))

    
    u.dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_normal_messages))
    u.dispatcher.add_error_handler(error)

    logger.info("Started polling for updates")
    u.start_polling()
