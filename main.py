from _secrets import secrets_bot_token, banned_user_ids, secrets_chat_ids
import logging
import logging.handlers
import traceback
from telegram import Update, ReactionTypeEmoji, ReactionTypeCustomEmoji, ReactionType, Bot
from telegram.ext import Application, ApplicationBuilder, ApplicationHandlerStop, CallbackContext, CommandHandler, filters, MessageHandler, TypeHandler, MessageReactionHandler
from telegram.constants import ParseMode
import re
import random
import markov
import slap_game
import jerk_of_the_day
import rps_game
import connect_four
import party
import hangman
import random_cope
import db
from db import M, MR
import getval
import taki
import mentions
import opinion
import chalice
import uptime
import talk
import stats
import pyrun
from utils import PUNCTUATION_REGEX, CommandTrigger, fill_usernames
import time

rfh = logging.handlers.RotatingFileHandler(filename='debug.log', mode='w', maxBytes=2*1024*1024, backupCount=0,)
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s',
                    level=logging.INFO, handlers=[rfh, logging.StreamHandler()])
logger = logging.getLogger(__name__)

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


last_auto_react_time: float = 0

async def handle_reactions(update: Update, context: CallbackContext):
    if update.message_reaction is None or update.message_reaction.user is None:
        return

    global last_auto_react_time


    def bot_has_no_reaction(message_id: int, bot_id: int) -> bool:
        reaction = db.get().execute(f"SELECT {MR.MSG_ID}, {MR.EMOJI} FROM {MR.TABLE} WHERE {MR.MSG_ID}=? AND {MR.USER_ID}=?", (message_id, bot_id)).fetchone()
        return reaction is None

    def is_message_not_from_bot(message_id: int, bot_id: int) -> bool:
        msg = db.get().execute(f"SELECT {M.MSG_ID}, {M.USER_ID} FROM {M.TABLE} WHERE {M.MSG_ID}=?", (message_id,)).fetchone()
        return msg and msg[M.USER_ID] != bot_id

    auto_react_chance = 0.001 # 1 in 1000
    auto_react_cooldown = 60 * 10 # 10 minutes
    approved_auto_react_emojis = ["😁", "🔥", "🎉", "🐳", "🌭", "🏆", "🍓", "💋", "😈", "👨‍💻", "🎅", "🎄", "☃", "💅", "👾",]
    if update.message_reaction.user.id not in banned_user_ids:
        def get_reaction_set(reactions: tuple[ReactionType, ...]) -> set[str]:
            result: set[str] = set()
            for r in reactions:
                if isinstance(r, ReactionTypeEmoji):
                    result.add(r.emoji)
                elif isinstance(r, ReactionTypeCustomEmoji):
                    result.add(r.custom_emoji_id)
            return result

        old = get_reaction_set(update.message_reaction.old_reaction)
        new = get_reaction_set(update.message_reaction.new_reaction)
        user_id = update.message_reaction.user.id
        msg_id = update.message_reaction.message_id
        ts = int(update.message_reaction.date.timestamp())
        added = new - old
        removed = old - new
        logger.info(f"New reactions: {added}, removed reactions: {removed} for msg {msg_id}")
        db.get().record_reaction(msg_id, user_id, ts, added, removed)

        bot = context.bot
        if isinstance(bot, Bot):
            auto_react_emoji = list(added)[0] if len(added) > 0 else None
            now = time.time()
            diff_seconds = now - last_auto_react_time
            if (
                random.random() < auto_react_chance and diff_seconds > auto_react_cooldown
                and auto_react_emoji and auto_react_emoji in approved_auto_react_emojis
                and bot_has_no_reaction(msg_id, bot.id) and is_message_not_from_bot(msg_id, bot.id)
            ):
                logger.info(f"Auto reacting with {auto_react_emoji} to {msg_id}")
                last_auto_react_time = now
                await bot.set_message_reaction(update.message_reaction.chat.id, msg_id, auto_react_emoji)
                db.get().record_reaction(msg_id, bot.id, ts, set(auto_react_emoji), set())
    else:
        logger.info(f"  Reaction from banned user {update.message_reaction.user.id}. Ignored.")


async def debug_file_id(update: Update, context: CallbackContext):
    if update.message.sticker is not None:
        logger.info(f"{update.message.sticker.file_id}")
    elif update.message.animation is not None:
        logger.info(f"{update.message.animation.file_id}")


async def handle_custom_command(update: Update, context: CallbackContext):
    logger.info(f"[custom] {update.message.text}")
    if (match := re.match(r'(/[^\s@]+)', update.message.text)) is None:
        return
    key = match.group(1).strip()

    if (val := getval.get_val(key)) is None:
        return

    await getval.send_val(update.get_bot(), CommandTrigger.from_update(update), key, val, show_header=False)


def again_setter(func):
    global again_function
    again_function = func


async def post_init(a: Application) -> None:
    logger.info(f"Checking for missing usernames")
    missing, filled = await fill_usernames(a.bot)
    if missing:
        logger.info(f"Filled {filled}/{missing} missing usernames")

    getval.start_tget_poller(a.bot)

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
        ("uptime", "total time I've been running with no sleep"),
        ("glazestats", "[person] who is glazing whom rn, optionally focusing on this person"),
        ("tget", "<minutes> <key> delay /get by this many minutes"),
        ("py", "<code> run a python script"),
        ("pyundo", "undo your last script"),
    ])


if __name__ == '__main__':
    logger.info("Connecting to database")
    db.init('bot.db')

    logger.info("Setting up telegram bot")
    a = ApplicationBuilder().token(secrets_bot_token).post_init(post_init).build()

    logger.info("Setting up command handlers")
    a.add_handler(TypeHandler(Update, whitelist_gate), group=-1)

    a.add_handler(MessageReactionHandler(handle_reactions))

    a.add_handler(CommandHandler("ping", ping))
    getval.subscribe(a, again_setter)
    a.add_handler(CommandHandler(("explain", "e"), explain))
    opinion.subscribe(a, again_setter)
    a.add_handler(CommandHandler("contribute", contribute))
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
    stats.subscribe(a)
    talk.subscribe(a, again_setter)
    pyrun.subscribe(a)


    a.add_handler(CommandHandler("test", lambda update, context: test(update, context)))

    a.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.FORWARDED, handle_normal_messages))
    #a.add_handler(MessageHandler(filters.Sticker.ALL | filters.ANIMATION, debug_file_id))
    # Unknown /commands are looked up as keys, so this has to be added last
    a.add_handler(MessageHandler(filters.COMMAND, handle_custom_command))
    a.add_error_handler(error)

    logger.info("Started polling for updates")
    a.run_polling(allowed_updates=Update.ALL_TYPES)
