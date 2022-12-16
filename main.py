from _secrets import secrets_bot_token, banned_user_ids
import logging
from telegram import ParseMode, Update
from telegram.ext import Updater, CommandHandler, Filters, MessageHandler
import re
import json
import random
import markovify
import slap_game
import jerk_of_the_day
import redis_db
from utils import in_whitelist
import difflib

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

r = redis_db.connect()
DICTIONARY_HASH = 'dictionary'
RECEIVED_MESSAGES_LIST = 'received_messages_list'
MESSAGES = []
MAX_ITERS = 999_999
# Don't include apostrophe
PUNCTUATION_REGEX = re.compile(r'[\s{}]+'.format(re.escape(r'!"#$%&()*+, -./:;<=>?@[\]^_`{|}~')))
ENDINGS_REGEX = re.compile(r"(?:ах|а|ев|ей|е|ов|о|иях|ия|ие|ий|й|ь|ы|ии|и|ях|я|у|ых|их|s)$", re.IGNORECASE)

again_function = None
markovify_model = None


def ping(update: Update, context):
    update.message.reply_text("Понг!", quote=True)


def test(update: Update, context):
    if (not in_whitelist(update)):
        return
    update.message.reply_text("Looking cool joker!", quote=False)


def shitpost(update: Update, context):
    if (not in_whitelist(update)):
        return
    logger.info(f"[shitpost] {update.message.text}")
    if markovify_model == None:
        update.message.reply_text("Прости, мне сегодня не до щитпостов...", quote=True)
        return
    match = re.match(r'/[\S]+\s+(.+)', update.message.text)
    if (match == None):
        text = markovify_model.make_sentence(max_words=20, tries=15)
        #text = markovify_model.make_short_sentence(140)
        update.message.reply_text(text, quote=False)
    else:
        try:
            start = match.group(1)
            text = markovify_model.make_sentence_with_start(start, strict=False, max_words=20, tries=15)
            global again_function
            again_function = lambda: shitpost(update, context)
            update.message.reply_text(text, quote=False)
        except:
            #update.message.reply_text("Бро, я сдаюсь, ты меня перещитпостил", quote=False)
            text = markovify_model.make_sentence(max_words=20, tries=15)
            update.message.reply_text(text, quote=False)


def dice(update: Update, context):
    update.message.reply_dice(quote=False)

    
def casino(update: Update, context):
    update.message.reply_dice(emoji="🎰", quote=False)


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
    
    if val is None:
        keys = list(r.hgetall(DICTIONARY_HASH).keys())
        close_matches = difflib.get_close_matches(key, keys, n=1)
        if len(close_matches) > 0:
            key = close_matches[0]
            val = r.hget(DICTIONARY_HASH, key)
        
    if val is None:
        update.message.reply_text("Не помню такого", quote=True)
        return
    update.message.reply_text(f"{key}\n{val}", quote=False)


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
        update.message.reply_text(f"Запомнил {key}! Раньше там было \"{old_value}\"", quote=False)
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


# Returns index of word that starts the definition
def deep_sentence_matches_definition(definition: str, sentence: list) -> int:
    for i in range(0, len(sentence) - len(definition) + 1):
        if (sentence_matches_definition(definition, sentence[i:i + len(definition)])):
            return i
    return -1


def explain(update: Update, context, beta=False):
    if (not in_whitelist(update)):
        return
    logger.info(f"[explain] {update.message.text}")
    match = re.match(r'/[\S]+\s+([\S]+)', update.message.text)
    if (match == None):
        update.message.reply_text("Что тебе объяснить?", quote=True)
        return
    global again_function
    again_function = lambda: explain(update, context, beta)
    definition = match.group(1)
    result = None
    shuffled_messages = MESSAGES.copy()
    random.shuffle(shuffled_messages)
    for rnd_message in shuffled_messages:
        words = [w for w in PUNCTUATION_REGEX.split(rnd_message) if w != ""]
        if (beta):
            starting_index = deep_sentence_matches_definition(definition, words)
            if (starting_index >= 0):
                result = " ".join(words[starting_index: starting_index + len(definition)])
                break
        elif (sentence_matches_definition(definition, words)):
            result = rnd_message
            break

    if (result == None):
        if not beta:
            logger.info("   Retrying with deep search")
            explain(update, context, beta=True)
        else:
            update.message.reply_text(f"Я не знаю что такое \"{definition}\" ._.", quote=False)
        return
    logger.info(f"  Result: {result}")
    update.message.reply_text(f"<b>{definition}</b>\n{result}", parse_mode=ParseMode.HTML, quote=False)


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
        #if (all(thing in lower_message for thing in things)):
        # Only search for matches at the begining of words
        if (len(rnd_message) <= 500 and all(re.search(r'(?:[\s{}]+|^){}'.format(re.escape(r'!"#$%&()*+, -./:;<=>?@[\]^_`{|}~'), re.escape(thing)), lower_message) for thing in things)):
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
        must_start_with = match.group(1)
    keys = list(r.hgetall(DICTIONARY_HASH).keys())
    if must_start_with != "":
        keys = [key for key in keys if key.lower().startswith(must_start_with.lower())]
    keys.sort()
    if (len(keys) == 0):
        if (must_start_with != ""):
            update.message.reply_text(f"Не нашел никаких гетов, начинающихся на \"{must_start_with}\" >.>", quote=False)
            return
        else:
            update.message.reply_text(f"Я пока не знаю никаких гетов... Но ты можешь их добавить командой /set!", quote=False)
            return
    header = 'Так вот же все ГЕТЫ:\n\n' if must_start_with == "" else f'Вот все ГЕТЫ, начинающиеся с \"{must_start_with}\":\n\n'
    response = ", ".join(keys)
    update.message.reply_text(header + response, quote=False)


def error(update: Update, context):
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def again(update: Update, context):
    if (not in_whitelist(update)):
        return
    if again_function:
        try:
            again_function()
        except:
            update.message.reply_text("А что /again? Кажется я все забыл...", quote=False)
    else:
        update.message.reply_text("А что /again? Кажется я все забыл...", quote=False)

def handle_normal_messages(update: Update, context):
    if (not in_whitelist(update, send_warning=False)):
        return
    logger.info(f"[msg] {update.message.text}")
    if (update.message.from_user.id in banned_user_ids):
        logger.info(f"  From banned user {update.message.from_user.id}. Ignored.")
    redis_db.update_user_data(update.message.from_user.id, update.message.from_user.username)
    r.rpush(RECEIVED_MESSAGES_LIST, update.message.text)
    MESSAGES.append(update.message.text)

if __name__ == '__main__':
    logger.info("Parsing messages...")
    f = open('_secrets/messages.json')
    data = json.load(f)
    banned_user_ids_str = [str(id) for id in banned_user_ids]
    for message in data['messages']:
        if ("text_entities" in message):
            text = "".join([txt.get("text") for txt in message.get("text_entities")])
            # Ignore commands and messages from banned users
            # Skip "user" prefix from id... Telegram export does this for some reason
            if (text != "" and "from_id" in message and message['from_id'][4:] not in banned_user_ids_str and not text.startswith("/")):
                MESSAGES.append(text)
    f.close()

    for message in r.lrange(RECEIVED_MESSAGES_LIST, 0, -1):
        MESSAGES.append(message)
    
    if (len(MESSAGES) == 0):
        # The bot assumes that the messages list is never empty so if there is none we put a default message there
        MESSAGES.append("Привет!")

    logger.info("Loading shitpost model...")
    markovify_model = markovify.Text("\n".join(MESSAGES))

    logger.info("Setting up telegram bot")
    u = Updater(secrets_bot_token, use_context=True)

    u.dispatcher.add_handler(CommandHandler("ping", ping))
    u.dispatcher.add_handler(CommandHandler("get", getDict))
    u.dispatcher.add_handler(CommandHandler("set", setDict))
    u.dispatcher.add_handler(CommandHandler(("explain", "e"), lambda update, context: explain(update, context, False)))
    u.dispatcher.add_handler(CommandHandler(("explainbeta", "eb"), lambda update, context: explain(update, context, True)))
    u.dispatcher.add_handler(CommandHandler("talk", talk))
    u.dispatcher.add_handler(CommandHandler(("opinion", "o"), opinion))
    u.dispatcher.add_handler(CommandHandler("contribute", contribute))
    u.dispatcher.add_handler(CommandHandler("getall", getAll))
    u.dispatcher.add_handler(CommandHandler("del", delDict))
    u.dispatcher.add_handler(CommandHandler(("again", "a"), again))
    u.dispatcher.add_handler(CommandHandler("dice", dice))
    u.dispatcher.add_handler(CommandHandler(("slot", "casino"), casino))
    u.dispatcher.add_handler(CommandHandler(("shitpost", "s"), shitpost))
    jerk_of_the_day.subscribe(u)
    slap_game.subscribe(u)

    u.dispatcher.add_handler(CommandHandler("test", lambda update, context: test(update, context)))

    
    u.dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_normal_messages))
    u.dispatcher.add_error_handler(error)

    logger.info("Started polling for updates")
    u.start_polling()
