from _secrets import secrets_bot_token, secrets_chat_ids
import logging 
from telegram import ParseMode, Update
from telegram.ext import Updater, CommandHandler, Filters
import redis
import re
import json
import random
from string import punctuation

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

DICTIONARY_HASH = 'dictionary'
MESSAGES = []
MAX_ITERS = 999_999
PUNCTUATION_REGEX = re.compile(r'[\s{}]+'.format(re.escape(punctuation)))
ENDINGS_REGEX = re.compile(r"(?:ах|а|ев|ей|е|ов|о|иях|ия|ие|ий|й|ь|ы|ии|и|ях|я|у|ых|s)$", re.IGNORECASE)

def in_whitelist(update: Update) -> bool:
    if (update.message.chat_id not in secrets_chat_ids):
        print(f"Blacklisted chat id: {update.message.chat_id}")
        update.message.reply_text("This chat is not whitelisted")
        return False
    return True

def ping(update: Update, context):
    update.message.reply_text("meow", quote=True)

def test(update: Update, context):
    update.message.reply_text("Looking cool joker!")

def getDict(update: Update, context):
    if (not in_whitelist(update)):
         return
    print("Get")
    print(update.message.text)
    match = re.match(r'/get\s+([\S]+)', update.message.text)
    if (match == None):
        update.message.reply_text("no key provided")
        return
    key = match.group(1)
    val = r.hget(DICTIONARY_HASH, key)
    if (val == None):
        update.message.reply_text("None get")
        return
    update.message.reply_text(val.decode("utf-8"), quote=False)

def setDict(update: Update, context):
    if (not in_whitelist(update)):
         return
    print("Set")
    print(update.message.text)
    match = re.match(r'/set\s+([\S]+)\s+(.+)', update.message.text, re.DOTALL)
    if (match == None):
        print('match none')
        update.message.reply_text("match = none")
        return
        
    key = match.group(1)
    val = match.group(2)
    old_value = r.hget(DICTIONARY_HASH, key)
    r.hset(DICTIONARY_HASH, key, val)
    if (old_value != None):
        update.message.reply_text(f"Set success! Old value was \"{old_value.decode('utf-8')}\"", quote=False)
    else:
        update.message.reply_text(f"Set success!", quote=False)

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
    print("Explain")
    print(update.message.text)
    match = re.match(r'/explain\s+([\S]+)', update.message.text)
    if (match == None):
        update.message.reply_text("no key provided")
        return
    definition = match.group(1)
    print(definition)
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
    print(result)
    update.message.reply_text(f"*{definition}*\n{result}", parse_mode=ParseMode.MARKDOWN, quote=False)

def talk(update: Update, context):
    if (not in_whitelist(update)):
         return
    print("Talk")
    rnd_message = random.choice(MESSAGES)
    print(rnd_message)
    update.message.reply_text(rnd_message)

def opinion(update: Update, context):
    if (not in_whitelist(update)):
         return
    print("Opinion")
    print(update.message.text)
    match = re.match(r'/opinion\s+(.+)', update.message.text)
    if (match == None):
        update.message.reply_text("О чем ты хотел узнать мое мнение?")
        return
    user_input = match.group(1)
    things = [thing for thing in re.split(r'\s', user_input) if thing != ""]
    things = [ENDINGS_REGEX.sub("", thing) for thing in things]
    print(things)
    shuffled_messages = MESSAGES.copy()
    random.shuffle(shuffled_messages)
    for rnd_message in shuffled_messages:
        if (all(thing in rnd_message for thing in things)):
            update.message.reply_text(rnd_message, quote=True)
            return
    update.message.reply_text(f"Я ничего не знаю о \"{user_input}\" >_<", quote=False)

def error(update, context):
    logger.warning('Update "%s" caused error "%s"', update, context.error)

#TODO log messages that are not commands
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

    logger.info("Setting up telegram bot")
    u = Updater(secrets_bot_token, use_context=True)

    u.dispatcher.add_handler(CommandHandler("ping", ping))
    u.dispatcher.add_handler(CommandHandler("get", getDict))
    u.dispatcher.add_handler(CommandHandler("set", setDict))
    u.dispatcher.add_handler(CommandHandler("explain", explain))
    u.dispatcher.add_handler(CommandHandler("talk", talk))
    u.dispatcher.add_handler(CommandHandler("opinion", opinion))
    
    u.dispatcher.add_handler(CommandHandler("test", lambda update, context: test(update, context)))
    u.dispatcher.add_error_handler(error)

    logger.info("Polling for updates...")
    u.start_polling()