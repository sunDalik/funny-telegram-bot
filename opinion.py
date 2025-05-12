import logging
import logging.handlers
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import re
import random
import redis_db
from utils import in_whitelist, parse_userid

r = redis_db.connect()
logger = logging.getLogger(__name__)
again_setter = None
ENDINGS_REGEX = re.compile(r"(?:ах|а|ев|ей|е|ов|о|иях|ия|ие|ий|й|ь|ы|ии|и|ях|я|у|ых|их|s)$", re.IGNORECASE)


def handle_opinion(update: Update, context: CallbackContext):
    if (not in_whitelist(update)):
        return
    logger.info(f"[opinion] {update.message.text}")
    match = re.match(r'/[\S]+\s+(.+)', update.message.text)
    if match is None:
        update.message.reply_text("О чем ты хотел узнать мое мнение?", quote=True)
        return
    user_input = match.group(1)
    opinion(update, context, user_input, [], None)


def handle_opinion_of(update: Update, context):
    if (not in_whitelist(update)):
        return
    logger.info(f"[opinionof] {update.message.text}")
    match = re.match(r'/[\S]+\s+([\S]+)\s+(.+)', update.message.text, re.DOTALL)
    if match is None:
        match = re.match(r'/[\S]+\s+([\S]+)', update.message.text)
        if match and update.message.reply_to_message is not None:
            user_id = update.message.reply_to_message.from_user.id
            user_input = match.group(1)
        else:
            update.message.reply_text("Первым параметром идет имя человека, а потом топик, про который хочешь узнать мнение. Ничему тебя в школе не учили?", quote=True)
            return
    else:
        user_name = match.group(1)
        user_id = parse_userid(user_name, context)
        user_input = match.group(2)

        
    if user_id is not None and int(user_id) == context.bot.id:
        seed = user_input.strip().lower()
        my_random = random.Random()
        my_random.seed(seed)
        intro = random.choice([f"Что я думаю о \"{user_input}\"?", f"Мое мнение о \"{user_input}\"?", f"Меня спрашивают о \"{user_input}\"?"])
        kansou = random.choice(["Хмм...", "Нуу...", "", "Эээ...", "🤔"])
        results = [("Да ничего я не думаю об этом ._.", 25), ("Да мне как-то все равно...", 25), ("Думаю это супер! ❤️", 80), ("It's ok I guess...", 60), ("Мне нравится!", 100), ("Крутая вещь! 🔥", 30), ("Мне не очень нравится...", 80), ("Такое себе...", 30), ("Это моя самая любимая вещь! 🔥", 10), ("Я ненавижу это! 😡", 10), ("Это худшее, что когда либо было изобретено человечеством", 1),  ("Эта самая лучшая вещь во вселенной!", 1),]
        res = my_random.choices([x for x, w in results], weights=[w for x, w in results])[0]
        update.message.reply_text(f"{intro} {kansou}\n{res}", quote=False)
        return

    if user_id is None:
        update.message.reply_text(f"\"{user_name}\"? Не припоминаю таких", quote=True)
        return
    opinion(update, context, user_input, [], user_id)


def try_find_opinion(messages, things, from_user_id, previous_results, user_input):
    terrible_result = None
    long_result = None
    regexes = [re.compile(r'(?:[\s{}]+|^){}'.format(re.escape(r'!"#$%&()*+, -./:;<=>?@[\]^_`{|}~'), re.escape(thing)), flags=re.IGNORECASE) for thing in things]
    for rnd_message in messages:
        #if (all(thing in lower_message for thing in things)):
        # Only search for matches at the begining of words
        if all(re.search(regex, rnd_message.text) for regex in regexes) and rnd_message.text.lower() not in previous_results:
            if from_user_id is not None and rnd_message.uid != from_user_id:
                continue
            if user_input.lower() == rnd_message.text.lower():
                terrible_result = user_input
                continue

            if len(rnd_message.text) <= 550:
                return rnd_message.text
            else:
                long_result = rnd_message.text
    
    if long_result is not None:
        return long_result
    
    if terrible_result is not None:
        return terrible_result
    return None


def opinion(update: Update, context, user_input, previous_results=[], from_user_id=None):
    things = [thing for thing in re.split(r'\s+', user_input) if thing != ""]
    logger.info(f"  Parse result: {things}")
    shuffled_messages = [m for m in redis_db.messages]
    random.shuffle(shuffled_messages)
    result = None
    result = try_find_opinion(shuffled_messages, things, from_user_id, previous_results, user_input)

    # If not found anything, repeat but now without endings
    if result is None:
        things = [ENDINGS_REGEX.sub("", thing) for thing in things]
        result = try_find_opinion(shuffled_messages, things, from_user_id, previous_results, user_input)

    if result is None:
        if len(previous_results) > 0 and from_user_id is None:
            update.message.reply_text(f"Я уже все высказал, что я думаю о \"{user_input}\"", quote=False)
        elif len(previous_results) > 0 and from_user_id is not None:
            update.message.reply_text(f"Я уже все передал, что {redis_db.get_username_by_id(from_user_id)} думает о \"{user_input}\"", quote=False)
        elif from_user_id is not None:
            update.message.reply_text(f"Кажется {redis_db.get_username_by_id(from_user_id)} ничего не думает о \"{user_input}\" x_x", quote=False)
        else:
            update.message.reply_text(f"Я ничего не знаю о \"{user_input}\" >_<", quote=False)
        return
    
    if again_setter:
        again_setter(lambda: opinion(update, context, user_input, previous_results + [result.lower()], from_user_id))
    update.message.reply_text(result, quote=False)


def subscribe(u: Updater, _again_setter):
    u.dispatcher.add_handler(CommandHandler(("opinion", "o"), handle_opinion))
    u.dispatcher.add_handler(CommandHandler(("opinionof", "oo", "oof"), handle_opinion_of))
    global again_setter
    again_setter = _again_setter
