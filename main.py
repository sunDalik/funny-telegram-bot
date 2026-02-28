from _secrets import secrets_bot_token, banned_user_ids, secrets_chat_ids
import logging
import logging.handlers
import traceback
from telegram import Update, ReactionTypeEmoji
from telegram.ext import Application, ApplicationBuilder, ApplicationHandlerStop, CallbackContext, CommandHandler, filters, MessageHandler, TypeHandler, MessageReactionHandler
from telegram.constants import ParseMode
import re
import json
import random
import markov
import slap_game
import jerk_of_the_day
import rps_game
import connect_four
import party
import hangman
import random_cope
import redis_db
import db
from db import M
import taki
import mentions
import opinion
import chalice
import uptime
import talk
from utils import PUNCTUATION_REGEX
import difflib

rfh = logging.handlers.RotatingFileHandler(filename='debug.log', mode='w', maxBytes=2*1024*1024, backupCount=0,)
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s',
                    level=logging.INFO, handlers=[rfh, logging.StreamHandler()])
logger = logging.getLogger(__name__)

r = redis_db.connect()
DICTIONARY_HASH = 'dictionary'
MAX_ITERS = 999_999
POLL_PREFIX =  "#!/Poll"
STICKER_PREFIX =  "#!/Sticker"
GIF_PREFIX =  "#!/GifAnimation"
PHOTO_PREFIX =  "#!/PhotoFile"
CAPTION_DELIMITER =  "/*#!&!#*/"
VIDEO_PREFIX =  "#!/VideoFile"
VOICE_PREFIX =  "#!/VoiceMessage"
RND_GET_PREFIX =  "#!/RandomizedGet"

again_function = None


async def whitelist_gate(update: Update, context) -> None:
    # Updates without an effective_chat (like inline queries) pass through ungated
    if update.effective_chat is not None and update.effective_chat.id not in secrets_chat_ids:
        logger.warning(f"Chat not whitelisted: {update.effective_chat.id}")
        # Bots have a global limit of 30 messages per second
        # https://core.telegram.org/bots/faq#broadcasting-to-users
        # We don't want to enable ddos attacks for blacklisted chats so we don't message them anything
        if False:
            await update.effective_message.reply_text("This chat is not whitelisted")
        raise ApplicationHandlerStop

    # Cache username mapping
    if update.effective_user is not None:
        username = update.effective_user.username or update.effective_user.first_name
        if username:
            db.get().insert(db.User(user_id=update.effective_user.id, username=username))
            db.get().commit()


async def ping(update: Update, context: CallbackContext):
    await update.message.reply_text("Понг!", do_quote=True)


async def test(update: Update, context: CallbackContext):
    await update.message.reply_text("Looking cool joker!", do_quote=False)
    #print(update.message.link)
    #print(update.message.reply_to_message)
    #print(update.message.reply_to_message.document)
    #print(update.message.reply_to_message.animation)




async def dice(update: Update, context: CallbackContext):
    await update.message.reply_dice(do_quote=False)

    
async def casino(update: Update, context: CallbackContext):
    await update.message.reply_dice(emoji="🎰", do_quote=False)


async def contribute(update: Update, context: CallbackContext):
    await update.message.reply_text("https://github.com/sunDalik/funny-telegram-bot", do_quote=False)


async def getDict(update: Update, context: CallbackContext):
    logger.info(f"[getDict] {update.message.text}")
    match = re.match(r'/[\S]+\s+(.+)', update.message.text)
    if (match == None):
        await update.message.reply_text("Ты чего хочешь-то?", do_quote=True)
        return
    key = match.group(1).strip()
    key, val = get_close_value_by_key(key)

    if val is None:
        await update.message.reply_text("Не помню такого", do_quote=True)
        return
    await send_get_value(update, key, val, show_header=True)

async def rand_get(update: Update, context: CallbackContext, previous_results=[]):
    logger.info(f"[rand_get] {update.message.text}")
    match = re.match(r'/[\S]+\s+([\S]+)', update.message.text)
    if match is None:
        search_string = ""
    else:
        search_string = match.group(1)
    keys = list(r.hgetall(DICTIONARY_HASH).keys())
    keys = [key for key in keys if search_string.lower() in key.lower() and key not in previous_results]
    if len(keys) == 0:
        if len(previous_results) > 0:
            if search_string == "":
                await update.message.reply_text("Я уже выдал все, что я знаю T__T", do_quote=False)
            else:
                await update.message.reply_text(f"Я уже выдал все геты по запросу \"{search_string}\" T__T", do_quote=False)
        else:
            if search_string == "":
                await update.message.reply_text("Не могу найти ни одного гета...", do_quote=False)
            else:
                await update.message.reply_text(f"Не могу найти ни одного гета по запросу \"{search_string}\"...", do_quote=False)
        return
    key = random.choice(keys)
    value = r.hget(DICTIONARY_HASH, key)
    global again_function
    again_function = lambda: rand_get(update, context, previous_results + [key])
    await send_get_value(update, key, value, show_header=True)


async def rawGetDict(update: Update, context: CallbackContext):
    logger.info(f"[rawGetDict] {update.message.text}")
    match = re.match(r'/[\S]+\s+(.+)', update.message.text)
    if match is None:
        await update.message.reply_text("Ты чего хочешь-то?", do_quote=True)
        return
    key = match.group(1).strip()
    key, val = get_close_value_by_key(key)
        
    if val is None:
        await update.message.reply_text("Не помню такого", do_quote=True)
        return

    if val.startswith(RND_GET_PREFIX):
        await update.message.reply_text(f"/rndset {key} {val[len(RND_GET_PREFIX):]}", do_quote=False)
    else:
        await update.message.reply_text(f"/set {key} {val}", do_quote=False)

    
def get_close_value_by_key(key: str):
    val = r.hget(DICTIONARY_HASH, key)
    if val is None:
        keys = list(r.hgetall(DICTIONARY_HASH).keys())
        close_matches = difflib.get_close_matches(key, keys, n=1)
        if len(close_matches) > 0:
            key = close_matches[0]
            val = r.hget(DICTIONARY_HASH, key)
    return key, val

async def send_get_value(update: Update, key: str, val, show_header, recursion_level = 0):
    '''
     A very hacky solution that I dont like! I think all dictionary entries should be json values with a type and a value
     So instead of storing plain text we would store {"type": "text", "value": "This is my text"}
    '''
    if val is None:
        await update.message.reply_text(f"Что-то я не помню что такое {key} :<")
    elif val.startswith(POLL_PREFIX + "{"):
        poll_data = json.loads(val[len(POLL_PREFIX):])
        await update.message.reply_poll(poll_data.get("question", ""), poll_data.get("options", []), is_anonymous=poll_data.get("is_anonymous", False), allows_multiple_answers=poll_data.get("allows_multiple_answers", False), do_quote=False)
    elif val.startswith(STICKER_PREFIX):
        file_id = val[len(STICKER_PREFIX):]
        await update.message.reply_sticker(file_id, do_quote=False)
    elif val.startswith(GIF_PREFIX):
        file_id = val[len(GIF_PREFIX):]
        # reply_document should also work
        await update.message.reply_animation(file_id, do_quote=False)
    elif val.startswith(PHOTO_PREFIX):
        values = val[len(PHOTO_PREFIX):].split(CAPTION_DELIMITER, maxsplit=1)
        file_id = values[0]
        caption = values[1] if len(values) > 1 else ""
        await update.message.reply_photo(file_id, do_quote=False, caption=caption)
    elif val.startswith(VIDEO_PREFIX):
        values = val[len(VIDEO_PREFIX):].split(CAPTION_DELIMITER, maxsplit=1)
        file_id = values[0]
        caption = values[1] if len(values) > 1 else ""
        await update.message.reply_video(file_id, do_quote=False, caption=caption)
    elif val.startswith(VOICE_PREFIX):
        file_id = val[len(VOICE_PREFIX):]
        # reply_document should also work
        await update.message.reply_voice(file_id, do_quote=False)
    elif val.startswith(RND_GET_PREFIX):
        if recursion_level > 100:
            await update.message.reply_text("Мужик иди в задницу со своей рекурсией")
            return
        values = [thing for thing in re.split(r'\s+', val[len(RND_GET_PREFIX):]) if thing != ""]
        random.shuffle(values)
        sent_success = False
        # Send first non-None value
        for v in values:
            chosen_key = v
            chosen_key, chosen_value = get_close_value_by_key(chosen_key)
            if chosen_value is not None:
                sent_success = True
                await send_get_value(update, chosen_key, chosen_value, show_header=show_header, recursion_level=recursion_level + 1)
                break
        # If all values are None send the sad notification
        if not sent_success and len(values) >= 1:
            await send_get_value(update, values[0], None, show_header=show_header, recursion_level=recursion_level + 1)
    elif val == '🎲' or val == '🎯' or val == '🏀' or val == '⚽️' or val == '🎳' or val == '🎰':
        await update.message.reply_dice(emoji=val, do_quote=False)
    else:
        if show_header:
            await update.message.reply_text(f"{key}\n{val}", do_quote=False)
        else:
            await update.message.reply_text(f"{val}", do_quote=False)


async def rndSetDict(update: Update, context: CallbackContext):
    logger.info(f"[rndSetDict] {update.message.text}")
    match = re.match(r'/[\S]+\s+([\S]+)\s+(.+)', update.message.text, re.DOTALL)
    if match is None:
        match = re.match(r'/[\S]+\s+([\S]+)', update.message.text)
        if match and update.message.reply_to_message is not None and update.message.reply_to_message.text is not None:
            key = match.group(1)
            values_text = update.message.reply_to_message.text
        else:
            await update.message.reply_text("Что-то я ничего не понял. Тебе нужно написать в качестве значения разделенный пробелами список ключей, по которым будет делаться /get. Например /rndset key funnyget1 funnyget2 funnyget3", do_quote=True)
            return
    else:
        key = match.group(1)
        values_text = match.group(2)
    old_value = r.hget(DICTIONARY_HASH, key)
    r.hset(DICTIONARY_HASH, key, RND_GET_PREFIX + values_text)
    await send_confirm_set_value(update, key, old_value, False)


async def setDict(update: Update, context: CallbackContext):
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
            # Maybe we can unify this behavior IF all of the animations are stored in document?
            elif update.message.reply_to_message.document is not None and update.message.reply_to_message.document.mime_type == 'image/gif':
                val = GIF_PREFIX + update.message.reply_to_message.document.file_id
            elif update.message.reply_to_message.photo is not None and len(update.message.reply_to_message.photo) > 0:
                # Messages store photos in an array where the last object of an array is the highest resolution version of a photo
                file_id = update.message.reply_to_message.photo[-1].file_id
                caption = update.message.reply_to_message.caption
                if caption is None:
                    caption = ""
                val = PHOTO_PREFIX + file_id + CAPTION_DELIMITER + caption 
            elif update.message.reply_to_message.video is not None:
                file_id = update.message.reply_to_message.video.file_id
                caption = update.message.reply_to_message.caption
                if caption is None:
                    caption = ""
                val = VIDEO_PREFIX + file_id + CAPTION_DELIMITER + caption 
            elif update.message.reply_to_message.voice is not None:
                val = VOICE_PREFIX + update.message.reply_to_message.voice.file_id
            elif update.message.reply_to_message.text is not None:   
                val = update.message.reply_to_message.text
            elif update.message.reply_to_message.link is not None:
                set_as_link = True
                val = update.message.reply_to_message.link
            else:
                await update.message.reply_text("Что-то я ничего не понял...", do_quote=True)
                return
        else:
            await update.message.reply_text("Что-то я ничего не понял. Удали свой /set и напиши нормально", do_quote=True)
            return
    else:
        key = match.group(1)
        val = match.group(2)
    old_value = r.hget(DICTIONARY_HASH, key)
    r.hset(DICTIONARY_HASH, key, val)
    await send_confirm_set_value(update, key, old_value, set_as_link)


async def send_confirm_set_value(update: Update, key: str, old_value, set_as_link: bool):
    extra_text = " (ссылкой на сообщение)" if set_as_link else ""
    if old_value is not None:
        if old_value.startswith(POLL_PREFIX):
            await update.message.reply_text(f"Запомнил {key}{extra_text}! Раньше там был какой-то опрос", do_quote=False)
        elif old_value.startswith(STICKER_PREFIX):
            await update.message.reply_text(f"Запомнил {key}{extra_text}! Раньше там был какой-то стикер", do_quote=False)
        elif old_value.startswith(GIF_PREFIX):
            await update.message.reply_text(f"Запомнил {key}{extra_text}! Раньше там была какая-то гифка", do_quote=False)
        elif old_value.startswith(PHOTO_PREFIX):
            await update.message.reply_text(f"Запомнил {key}{extra_text}! Раньше там была какая-то картинка", do_quote=False)
        elif old_value.startswith(VIDEO_PREFIX):
            await update.message.reply_text(f"Запомнил {key}{extra_text}! Раньше там было какое-то видео", do_quote=False)
        elif old_value.startswith(VOICE_PREFIX):
            await update.message.reply_text(f"Запомнил {key}{extra_text}! Раньше там было какое-то голосовое", do_quote=False)
        elif old_value.startswith(RND_GET_PREFIX):
            await update.message.reply_text(f"Запомнил {key}{extra_text}! Раньше там было что-то рандомное", do_quote=False)
        else:
            output_limit = 100
            if len(old_value) > output_limit:
                await update.message.reply_text(f"Запомнил {key}{extra_text}! Раньше там было \"{old_value[0:output_limit]}...\" и т.д.", do_quote=False)
            else:
                await update.message.reply_text(f"Запомнил {key}{extra_text}! Раньше там было \"{old_value}\"", do_quote=False)
    else:
        await update.message.reply_text(f"Запомнил {key}{extra_text}!", do_quote=False)


async def delDict(update: Update, context: CallbackContext):
    logger.info(f"[delDict] {update.message.text}")
    match = re.match(r'/[\S]+\s+([\S]+)', update.message.text)
    if (match == None):
        await update.message.reply_text("Не понял, а что удалить-то хочешь?")
        return
    key = match.group(1)
    val = r.hdel(DICTIONARY_HASH, key)
    if (val == 0):
        await update.message.reply_text(f"Чего-чего? \"{key}\"? Я такого не знаю", do_quote=False)
    else:
        await update.message.reply_text(f"Ок, я удалил ключ \"{key}\"", do_quote=False)


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


async def explain(update: Update, context: CallbackContext, previous_results = []):
    logger.info(f"[explain] {update.message.text}")
    match = re.match(r'/[\S]+\s+(.+)', update.message.text)
    if match is None:
        if update.message.reply_to_message is not None and update.message.reply_to_message.text is not None:
            user_input = update.message.reply_to_message.text
        else:
            await update.message.reply_text("Что тебе объяснить?", do_quote=True)
            return
    else:
        user_input = match.group(1)
    definitions = [thing for thing in re.split(r'\s+', user_input) if thing != ""]
    result = ""
    found_explanation = False
    shuffled_messages = [r[M.TEXT] for r in db.get().execute(f"SELECT {M.TEXT} FROM {M.TABLE}")]
    for attempt in range(10):
        for definition in definitions:
            random.shuffle(shuffled_messages)
            curr_result = None
            for rnd_message in shuffled_messages:
                words = [w for w in PUNCTUATION_REGEX.split(rnd_message) if w != ""]
                if sentence_matches_definition(definition, words):
                    curr_result = rnd_message
                    if len(definitions) <= 1 and curr_result.lower() in previous_results:
                        curr_result = None
                    else:
                        break
 
            if curr_result is None:
                #logger.info(f"  Retrying with deep search...")
                for rnd_message in shuffled_messages:
                    words = [w for w in PUNCTUATION_REGEX.split(rnd_message) if w != ""]
                    starting_index = deep_sentence_matches_definition(definition, words)
                    if (starting_index >= 0):
                        curr_result = " ".join(words[starting_index: starting_index + len(definition)])
                        if len(definitions) <= 1 and curr_result.lower() in previous_results:
                            curr_result = None
                        else:
                            break
 
            if curr_result is not None:
                if result != "":
                    result += "  "
                result += curr_result
                found_explanation = True
            else:
                if result != "":
                    result += "  "
                result += definition
 
        # Attempting is only relevant for multi-explain. If we can't find a new explanation for a single definition then we will never be able to find it
        if len(definitions) <= 1:
            break
 
        # Multi-explain avoids repetitions in the ENTIRE result and not for separate definitions
        if result.lower() not in previous_results:
            break
 
        result = ""
        found_explanation = False
 
    if not found_explanation:
        if len(previous_results) > 0:
            await update.message.reply_text(f"Кажется я все уже объяснил про \"{user_input}\"", do_quote=False)
        else:
            await update.message.reply_text(f"Я не знаю, что такое \"{user_input}\" ._.", do_quote=False)
        return

    global again_function
    again_function = lambda: explain(update, context, previous_results + [result.lower()])
    logger.info(f"  Result: {result}")
    await update.message.reply_text(f"<b>{user_input}</b>\n{result}", parse_mode=ParseMode.HTML, do_quote=False)


async def getAll(update: Update, context: CallbackContext):
    logger.info("[getAll]")
    match = re.match(r'/[\S]+\s+([^\s]+)', update.message.text)
    search_string = ""
    if match:
        search_string = match.group(1)
    keys = list(r.hgetall(DICTIONARY_HASH).keys())
    if search_string != "":
        keys = [key for key in keys if search_string.lower() in key.lower()]
    keys.sort()
    if (len(keys) == 0):
        if (search_string != ""):
            await update.message.reply_text(f"Не нашел никаких гетов по запросу \"{search_string}\" >.>", do_quote=False)
            return
        else:
            await update.message.reply_text(f"Я пока не знаю никаких гетов... Но ты можешь их добавить командой /set!", do_quote=False)
            return
    header = 'Так вот же все ГЕТЫ:\n\n' if search_string == "" else f'Вот все ГЕТЫ с \"{search_string}\":\n\n'
    response = header + ", ".join(keys)
    # Telegram has a limit of 4096 characters per message and it doesn't split them automatically
    msgs = [response[i:i + 4096] for i in range(0, len(response), 4096)]
    for text in msgs:
        await update.message.reply_text(text, do_quote=False)

async def error(update: object, context: CallbackContext):
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    logger.warning('Exception in update "%s"\n%s\n%s', update, context.error, "".join(tb_list))


async def again(update: Update, context: CallbackContext):
    if again_function:
        try:
            await again_function()
        except:
            await update.message.reply_text("А что /again? Кажется я все забыл...", do_quote=False)
    else:
        await update.message.reply_text("А что /again? Кажется я все забыл...", do_quote=False)

async def handle_normal_messages(update: Update, context: CallbackContext):
    logger.info(f"[msg] {update.message.text}")
    if update.message.from_user.id not in banned_user_ids:
        db.get().record_message(update.message.message_id,
                                update.message.from_user.id,
                                int(update.message.date.timestamp()),
                                update.message.text)
    else:
        logger.info(f"  From banned user {update.message.from_user.id}. Ignored.")


async def handle_reactions(update: Update, context: CallbackContext):
    if update.message_reaction is None or update.message_reaction.user is None:
        return
    if update.message_reaction.user.id not in banned_user_ids:
        old = {r.emoji for r in update.message_reaction.old_reaction if isinstance(r, ReactionTypeEmoji)}
        new = {r.emoji for r in update.message_reaction.new_reaction if isinstance(r, ReactionTypeEmoji)}
        user_id = update.message_reaction.user.id
        ts = int(update.message_reaction.date.timestamp())
        db.get().record_reaction(update.message_reaction.message_id, user_id, ts, new - old, old - new)
    else:
        logger.info(f"  Reaction from banned user {update.message_reaction.user.id}. Ignored.")


async def debug_file_id(update: Update, context: CallbackContext):
    if update.message.sticker is not None:
        logger.info(f"{update.message.sticker.file_id}")
    elif update.message.animation is not None:
        logger.info(f"{update.message.animation.file_id}")


async def handle_custom_command(update: Update, context: CallbackContext):
    logger.info(f"[custom] {update.message.text}")
    match = re.match(r'(/[^\s@]+)', update.message.text)
    if match is None:
        return
    key = match.group(1).strip()
    val = r.hget(DICTIONARY_HASH, key)
    
    if val is None:
        return
    
    await send_get_value(update, key, val, show_header=False)


def again_setter(func):
    global again_function
    again_function = func


async def post_init(a: Application) -> None:
    await a.bot.set_my_commands([
        ("ping", "am I alive?"),
        ("get", "<key> get value by key"),
        ("set", "<key> <value> set value by key"),
        ("del", "<key> delete key"),
        ("getall", "[search] get all keys / get all keys that contain the search string"),
        ("randget", "[search] get value of a random key that contains the search string"),
        ("explain", "<definition> find a suitable explanation for the given definition"),
        ("opinion", "<thing> what's my opinion on thing?"),
        ("opinionof", "<person> <thing> what's person's opinion on thing?"),
        ("mentions", "<thing> count how many times thing was mentioned"),
        ("rndset", "<key> <value keys> add randomized key which uses the provided whitespace-separated list of keys"),
        ("rawget", "<key> get raw internal value by key"),
        ("shitpost", "[thing] generate a shitpost message using markov chain (optionally starting with [thing])"),
        ("talk", "[emojis] get a random message, optionally with at least this many emoji reactions"),
        ("talklike", "<person> [emojis] get a random message from this person, optionally with at least this many emoji reactions"),
        ("again", "repeat last /explain, /opinion or /randget"),
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
        ("taki", "[difficulty] play a game of taki"),
        ("takistats", "[difficulty] get all-time stats for taki"),
        ("chalice", "<thing> how full is the chalice of thing?"),
        ("uptime", "total time I've been running with no sleep")
    ])


if __name__ == '__main__':
    logger.info("Connecting to database")
    db.init('bot.db')

    logger.info("Setting up telegram bot")
    a = ApplicationBuilder().token(secrets_bot_token).post_init(post_init).build()

    a.add_handler(TypeHandler(Update, whitelist_gate), group=-1)

    a.add_handler(MessageReactionHandler(handle_reactions))

    a.add_handler(CommandHandler("ping", ping))
    a.add_handler(CommandHandler("get", getDict))
    a.add_handler(CommandHandler("rawget", rawGetDict))
    a.add_handler(CommandHandler("set", setDict))
    a.add_handler(CommandHandler("rndset", rndSetDict))
    a.add_handler(CommandHandler(("explain", "e"), explain))
    opinion.subscribe(a, again_setter)
    a.add_handler(CommandHandler("contribute", contribute))
    a.add_handler(CommandHandler("getall", getAll))
    a.add_handler(CommandHandler(("randget", "rg"), rand_get))
    a.add_handler(CommandHandler("del", delDict))
    a.add_handler(CommandHandler(("again", "a"), again))
    a.add_handler(CommandHandler("dice", dice))
    a.add_handler(CommandHandler(("slot", "casino"), casino))
    markov.subscribe(a, again_setter)
    jerk_of_the_day.subscribe(a)
    slap_game.subscribe(a)
    rps_game.subscribe(a)
    connect_four.subscribe(a)
    hangman.subscribe(a)
    random_cope.subscribe(a)
    party.subscribe(a)
    taki.subscribe(a, again_setter)
    mentions.subscribe(a)
    chalice.subscribe(a)
    uptime.subscribe(a)
    talk.subscribe(a, again_setter)


    a.add_handler(CommandHandler("test", lambda update, context: test(update, context)))

    a.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.FORWARDED, handle_normal_messages))
    #a.add_handler(MessageHandler(filters.Sticker.ALL | filters.ANIMATION, debug_file_id))
    a.add_handler(MessageHandler(filters.COMMAND, handle_custom_command))
    a.add_error_handler(error)

    logger.info("Started polling for updates")
    a.run_polling(allowed_updates=Update.ALL_TYPES)
