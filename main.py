from _secrets import secrets_bot_token, banned_user_ids
import logging
import logging.handlers
from telegram import ParseMode, Update
from telegram.ext import Updater, CommandHandler, Filters, MessageHandler
import re
import json
import random
import markovify
import slap_game
import jerk_of_the_day
import rps_game
import connect_four
import party
import hangman
import random_cope
import redis_db
from utils import in_whitelist, PUNCTUATION_REGEX
import difflib

rfh = logging.handlers.RotatingFileHandler(filename='debug.log', mode='w', maxBytes=2*1024*1024, backupCount=0,)
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s',
                    level=logging.INFO, handlers=[rfh, logging.StreamHandler()])
logger = logging.getLogger(__name__)

r = redis_db.connect()
DICTIONARY_HASH = 'dictionary'
MAX_ITERS = 999_999
ENDINGS_REGEX = re.compile(r"(?:ах|а|ев|ей|е|ов|о|иях|ия|ие|ий|й|ь|ы|ии|и|ях|я|у|ых|их|s)$", re.IGNORECASE)
POLL_PREFIX =  "#!/Poll"
STICKER_PREFIX =  "#!/Sticker"
GIF_PREFIX =  "#!/GifAnimation"
PHOTO_PREFIX =  "#!/PhotoFile"
CAPTION_DELIMITER =  "/*#!&!#*/"

again_function = None
markovify_model = None


def ping(update: Update, context):
    update.message.reply_text("Понг!", quote=True)


def test(update: Update, context):
    if (not in_whitelist(update)):
        return
    update.message.reply_text("Looking cool joker!", quote=False)
    #print(update.message.link)
    #print(update.message.reply_to_message.document)
    #print(update.message.reply_to_message.animation)


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
    match = re.match(r'/[\S]+\s+(.+)', update.message.text)
    if (match == None):
        update.message.reply_text("Ты чего хочешь-то?", quote=True)
        return
    key = match.group(1).strip()
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
    
    '''
     A very hacky solution that I dont like! I think all dictionary entries should be json values with a type and a value
     So instead of storing plain text we would store {"type": "text", "value": "This is my text"}
    '''
    if val.startswith(POLL_PREFIX + "{"):
        poll_data = json.loads(val[len(POLL_PREFIX):])
        update.message.reply_poll(poll_data.get("question", ""), poll_data.get("options", []), is_anonymous=poll_data.get("is_anonymous", False), allows_multiple_answers=poll_data.get("allows_multiple_answers", False), quote=False)
    elif val.startswith(STICKER_PREFIX):
        file_id = val[len(STICKER_PREFIX):]
        update.message.reply_sticker(file_id, quote=False)
    elif val.startswith(GIF_PREFIX):
        file_id = val[len(GIF_PREFIX):]
        # reply_document should also work
        update.message.reply_animation(file_id, quote=False)
    elif val.startswith(PHOTO_PREFIX):
        values = val[len(PHOTO_PREFIX):].split(CAPTION_DELIMITER, maxsplit=1)
        file_id = values[0]
        caption = values[1] if len(values) > 1 else ""
        update.message.reply_photo(file_id, quote=False, caption=caption)
    else:
        update.message.reply_text(f"{key}\n{val}", quote=False)


def setDict(update: Update, context):
    if (not in_whitelist(update)):
        return
    logger.info(f"[setDict] {update.message.text}")
    match = re.match(r'/[\S]+\s+([\S]+)\s+(.+)', update.message.text, re.DOTALL)
    set_as_link = False
    if match is None:
        match = re.match(r'/[\S]+\s+([\S]+)', update.message.text)
        if match and update.message.reply_to_message is not None:
            key = match.group(1)
            poll = update.message.reply_to_message.poll
            if poll is not None:
                poll_json = {"question": poll.question, "options": [option.text for option in poll.options], "is_anonymous": poll.is_anonymous, "allows_multiple_answers": poll.allows_multiple_answers}
                val = POLL_PREFIX + json.dumps(poll_json)
            elif update.message.reply_to_message.sticker is not None:
                # It's important to note that file_ids are persistent BUT they can't be shared between bots. So it's impossible to fully port the database from one bot to another
                # file_unique_ids are persistent between bots but you can't send or download them so they are useless
                val = STICKER_PREFIX + update.message.reply_to_message.sticker.file_id
            elif update.message.reply_to_message.animation is not None:
                val = GIF_PREFIX + update.message.reply_to_message.animation.file_id
            # I don't know why but some GIF animations are only stored in .document but not in .animation even though they behave the same
            elif update.message.reply_to_message.document is not None and update.message.reply_to_message.document.mime_type == 'image/gif':
                val = GIF_PREFIX + update.message.reply_to_message.document.file_id
            elif update.message.reply_to_message.photo is not None and len(update.message.reply_to_message.photo) > 0:
                # Messages store photos in an array where the last object of an array is the highest resolution version of a photo
                file_id = update.message.reply_to_message.photo[-1].file_id
                caption = update.message.reply_to_message.caption
                if caption is None:
                    caption = ""
                val = PHOTO_PREFIX + file_id + CAPTION_DELIMITER + caption 
            elif update.message.reply_to_message.text is not None:   
                val = update.message.reply_to_message.text
            elif update.message.reply_to_message.link is not None:
                set_as_link = True
                val = update.message.reply_to_message.link
            else:
                update.message.reply_text("Что-то я ничего не понял...", quote=True)
                return
        else:
            update.message.reply_text("Что-то я ничего не понял. Удали свой /set и напиши нормально", quote=True)
            return
    else:
        key = match.group(1)
        val = match.group(2)
    old_value = r.hget(DICTIONARY_HASH, key)
    r.hset(DICTIONARY_HASH, key, val)
    extra_text = " (ссылкой на сообщение)" if set_as_link else ""
    if old_value is not None:
        if old_value.startswith(POLL_PREFIX):
            update.message.reply_text(f"Запомнил {key}{extra_text}! Раньше там был какой-то опрос", quote=False)
        elif old_value.startswith(STICKER_PREFIX):
            update.message.reply_text(f"Запомнил {key}{extra_text}! Раньше там был какой-то стикер", quote=False)
        elif old_value.startswith(GIF_PREFIX):
            update.message.reply_text(f"Запомнил {key}{extra_text}! Раньше там была какая-то гифка", quote=False)
        elif old_value.startswith(PHOTO_PREFIX):
            update.message.reply_text(f"Запомнил {key}{extra_text}! Раньше там была какая-то картинка", quote=False)
        else:
            update.message.reply_text(f"Запомнил {key}{extra_text}! Раньше там было \"{old_value}\"", quote=False)
    else:
        update.message.reply_text(f"Запомнил {key}{extra_text}!", quote=False)

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
    shuffled_messages = redis_db.messages.copy()
    random.shuffle(shuffled_messages)
    for rnd_message in shuffled_messages:
        words = [w for w in PUNCTUATION_REGEX.split(rnd_message) if w != ""]
        if sentence_matches_definition(definition, words):
            result = rnd_message
            break
    
    if result is None:
        logger.info(f"  Retrying with deep search...")
        for rnd_message in shuffled_messages:
            words = [w for w in PUNCTUATION_REGEX.split(rnd_message) if w != ""]
            starting_index = deep_sentence_matches_definition(definition, words)
            if (starting_index >= 0):
                result = " ".join(words[starting_index: starting_index + len(definition)])
                break

    if result is None:
        update.message.reply_text(f"Я не знаю что такое \"{definition}\" ._.", quote=False)
        return
    logger.info(f"  Result: {result}")
    update.message.reply_text(f"<b>{definition}</b>\n{result}", parse_mode=ParseMode.HTML, quote=False)


def talk(update: Update, context):
    if (not in_whitelist(update)):
        return
    logger.info("[talk]")
    rnd_message = random.choice(redis_db.messages)
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
    shuffled_messages = redis_db.messages.copy()
    random.shuffle(shuffled_messages)
    for rnd_message in shuffled_messages:
        lower_message = rnd_message.lower()
        #if (all(thing in lower_message for thing in things)):
        # Only search for matches at the begining of words
        if (len(rnd_message) <= 550 and all(re.search(r'(?:[\s{}]+|^){}'.format(re.escape(r'!"#$%&()*+, -./:;<=>?@[\]^_`{|}~'), re.escape(thing)), lower_message) for thing in things)):
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
    response = header + ", ".join(keys)
    # Telegram has a limit of 4096 characters per message and it doesn't split them automatically
    msgs = [response[i:i + 4096] for i in range(0, len(response), 4096)]
    for text in msgs:
        update.message.reply_text(text, quote=False)


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
    redis_db.update_user_data(update.message.from_user)
    r.rpush(redis_db.RECEIVED_MESSAGES_LIST, update.message.text)
    redis_db.messages.append(update.message.text)


def debug_file_id(update: Update, context):
    if (not in_whitelist(update, send_warning=False)):
        return
    if update.message.sticker is not None:
        logger.info(f"{update.message.sticker.file_id}")
    elif update.message.animation is not None:
        logger.info(f"{update.message.animation.file_id}")


if __name__ == '__main__':
    logger.info("Parsing messages...")
    redis_db.load_messages()

    logger.info("Loading shitpost model...")
    markovify_model = markovify.Text("\n".join(redis_db.messages))

    logger.info("Setting up telegram bot")
    u = Updater(secrets_bot_token, use_context=True)

    u.dispatcher.add_handler(CommandHandler("ping", ping))
    u.dispatcher.add_handler(CommandHandler("get", getDict))
    u.dispatcher.add_handler(CommandHandler("set", setDict))
    u.dispatcher.add_handler(CommandHandler(("explain", "e"), explain))
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
    rps_game.subscribe(u)
    connect_four.subscribe(u)
    hangman.subscribe(u)
    random_cope.subscribe(u)
    party.subscribe(u)


    u.dispatcher.add_handler(CommandHandler("test", lambda update, context: test(update, context)))
    
    u.dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_normal_messages))
    #u.dispatcher.add_handler(MessageHandler(Filters.sticker | Filters.animation, debug_file_id))
    u.dispatcher.add_error_handler(error)

    u.bot.set_my_commands([
        ("ping", "am I alive?"),
        ("get", "<key> get value by key"),
        ("set", "<key> <value> set value by key"),
        ("del", "<key> delete key"),
        ("getall", "[search] get all keys / get all keys starting with search"),
        ("explain", "<definition> find a suitable explanation for the given definition"),
        ("opinion", "<thing> what's my opinion on thing?"),
        ("shitpost", "[thing] generate a shitpost message using markov chain (optionally starting with [thing])"),
        ("talk", "get random message"),
        ("again", "repeat last /explain or /opinion"),
        ("reg", "register for the \"jerk of the day\" game"),
        ("unreg", "unregister from the \"jerk of the day\" game"),
        ("jerk", "roll \"jerk of the day\""),
        ("jerkstats", "get all-time stats for the \"jerk of the day\""),
        ("jerkall", "get a list of all users registered for the \"jerk of the day\""),
        ("slap", "<person> slap person and reduce their slap-score by 1"),
        ("heal", "<person> heal person to increase their slap-score by 1 and cure vulnerability"),
        ("parry", "parry a slap within a minute to block it"),
        ("slapstats", "get all-time stats for the slap-game"),
        ("slaprules", "review rules of the slap-game"),
        ("rps", "[person] play a rock-paper-scissors game with person"),
        ("cf", "[person] play a Connect 4 game with person"),
        ("hangman", "play a Hangman game with the chat [RU]"),
        ("hangman_english", "play a Hangman game with the chat [EN]"),
        ("dice", "roll the dice"),
        ("slot", "gambling time"),
        ("cope", "how hard can you cope?"),
        ("contribute", "get github link"),
        ("partycreate", "<name> <people count for notification> create a new party"),
        ("partylist", "show all parties"),
        ("party", "<name> join party"),
        ("partydelete", "<name> delete a party"),
        ("partypingunregister", "<name> unregister for notifications in /partypinginvite"),
        ("partyleave", "<name> leave a party"),
        ("partyping", "<name> ping all current party members"),
        ("partypinginvite", "<name> ping all former party members that are not joined now"),
        ("partyinfo", "<name> get info about game party"),
    ])

    logger.info("Started polling for updates")
    u.start_polling()
