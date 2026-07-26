from _secrets import banned_user_ids
from telegram import Bot, Update, ReplyParameters
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackContext, CommandHandler
import asyncio
import difflib
import json
import logging
import random
import re
import time
import db
from db import GV, GJ
from utils import CommandTrigger, fmt_linked_msg_html

logger = logging.getLogger(__name__)

TYPE_TEXT = "text"
TYPE_STICKER = "sticker"
TYPE_GIF = "gif"
TYPE_PHOTO = "photo"
TYPE_VIDEO = "video"
TYPE_VOICE = "voice"
TYPE_POLL = "poll"
TYPE_RND = "rnd"
TYPE_DICE = "dice"

RAW_PREFIXES = {
    TYPE_POLL: "#!/Poll",
    TYPE_STICKER: "#!/Sticker",
    TYPE_GIF: "#!/GifAnimation",
    TYPE_PHOTO: "#!/PhotoFile",
    TYPE_VIDEO: "#!/VideoFile",
    TYPE_VOICE: "#!/VoiceMessage",
    TYPE_RND: "#!/RandomizedGet",
}

REPLACE_VAL_LABELS = {
    TYPE_POLL: "был какой-то опрос",
    TYPE_STICKER: "был какой-то стикер",
    TYPE_GIF: "была какая-то гифка",
    TYPE_PHOTO: "была какая-то картинка",
    TYPE_VIDEO: "было какое-то видео",
    TYPE_VOICE: "было какое-то голосовое",
    TYPE_RND: "было что-то рандомное",
}

CAPTION_TYPES = (TYPE_GIF, TYPE_PHOTO, TYPE_VIDEO)
CAPTION_DELIMITER = "/*#!&!#*/"

DICE_EMOJIS = ('🎲', '🎯', '🏀', '⚽️', '🎳', '🎰')

again_setter = None


def _load_json(text: str) -> dict | None:
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except ValueError:
        return None


def parse_rawget(blob: str) -> tuple[str, str, str]:
    for type, prefix in RAW_PREFIXES.items():
        if not blob.startswith(prefix):
            continue
        payload = blob[len(prefix):]
        if type in CAPTION_TYPES:
            file_id, _, caption = payload.partition(CAPTION_DELIMITER)
            return type, file_id, caption
        return type, payload, ""
    if blob in DICE_EMOJIS:
        return TYPE_DICE, blob, ""
    return TYPE_TEXT, blob, ""


def fmt_rawget(type: str, data: str, caption: str = "") -> str:
    prefix = RAW_PREFIXES.get(type, "")
    if type in CAPTION_TYPES:
        return prefix + data + CAPTION_DELIMITER + caption
    return prefix + data


def parse_set_data(text: str) -> tuple[str, str, str]:
    return parse_rawget(text)


def get_val(key: str) -> db.GetVal | None:
    vals = db.get().fetch_many(db.GetVal, f"SELECT * FROM {GV.TABLE} WHERE {GV.KEY}=?", (key,))
    return vals[0] if vals else None


def get_close_val(key: str) -> db.GetVal | None:
    if (val := get_val(key)) is not None:
        return val
    if close_matches := difflib.get_close_matches(key, all_keys(), n=1):
        return get_val(close_matches[0])
    return None


def set_val(key: str, type: str, data: str, caption: str = "") -> db.GetVal | None:
    old = get_val(key)
    db.get().insert(db.GetVal(key=key, type=type, data=data, caption=caption))
    db.get().commit()
    return old


def del_val(key: str) -> bool:
    cursor = db.get().execute(f"DELETE FROM {GV.TABLE} WHERE {GV.KEY}=?", (key,))
    db.get().commit()
    return cursor.rowcount > 0


def all_keys(search: str = "") -> list[str]:
    rows = db.get().execute(f"SELECT {GV.KEY} FROM {GV.TABLE}").fetchall()
    keys = [row[GV.KEY] for row in rows]
    return [key for key in keys if search.lower() in key.lower()] if search != "" else keys


def vals_of_type(type: str) -> list[db.GetVal]:
    return db.get().fetch_many(db.GetVal, f"SELECT * FROM {GV.TABLE} WHERE {GV.TYPE}=?", (type,))


async def send_val(bot: Bot, trigger: CommandTrigger, key: str, val: db.GetVal | None,
                   show_header: bool, recursion_level: int = 0):
    if val is None:
        await bot.send_message(trigger.chat_id, f"Что-то я не помню что такое {key} :<")
    elif val.type == TYPE_POLL:
        poll_data = _load_json(val.data) or {}
        await bot.send_poll(trigger.chat_id, poll_data.get("question", ""), poll_data.get("options", []),
                            is_anonymous=poll_data.get("is_anonymous", False),
                            allows_multiple_answers=poll_data.get("allows_multiple_answers", False))
    elif val.type == TYPE_STICKER:
        await bot.send_sticker(trigger.chat_id, val.data)
    elif val.type == TYPE_GIF:
        await bot.send_animation(trigger.chat_id, val.data, caption=val.caption)
    elif val.type == TYPE_PHOTO:
        await bot.send_photo(trigger.chat_id, val.data, caption=val.caption)
    elif val.type == TYPE_VIDEO:
        await bot.send_video(trigger.chat_id, val.data, caption=val.caption)
    elif val.type == TYPE_VOICE:
        await bot.send_voice(trigger.chat_id, val.data)
    elif val.type == TYPE_DICE:
        await bot.send_dice(trigger.chat_id, emoji=val.data)
    elif val.type == TYPE_RND:
        if recursion_level > 100:
            await bot.send_message(trigger.chat_id, "Мужик иди в задницу со своей рекурсией")
            return
        keys = [thing for thing in re.split(r'\s+', val.data) if thing != ""]
        random.shuffle(keys)
        # Send the first key that resolves to something
        for chosen_key in keys:
            if (chosen := get_close_val(chosen_key)) is not None:
                await send_val(bot, trigger, chosen.key, chosen, show_header=show_header,
                               recursion_level=recursion_level + 1)
                return
        # If none of them do, send the sad notification
        if len(keys) >= 1:
            await send_val(bot, trigger, keys[0], None, show_header=show_header,
                           recursion_level=recursion_level + 1)
    else:
        await bot.send_message(trigger.chat_id, f"{key}\n{val.data}" if show_header else val.data)


async def send_get_response(bot: Bot, trigger: CommandTrigger, key: str, show_header: bool):
    if (val := get_close_val(key)) is not None:
        await send_val(bot, trigger, val.key, val, show_header=show_header)
    else:
        await bot.send_message(trigger.chat_id, "Не помню такого", reply_parameters=ReplyParameters(
            message_id=trigger.msg_id, allow_sending_without_reply=True))


async def handle_get(update: Update, context: CallbackContext):
    logger.info(f"[get] {update.message.text}")
    if (match := re.match(r'/[\S]+\s+(.+)', update.message.text)) is None:
        await update.message.reply_text("Ты чего хочешь-то?", do_quote=True)
        return
    key = match.group(1).strip()
    await send_get_response(update.get_bot(), CommandTrigger.from_update(update), key, show_header=True)


async def handle_randget(update: Update, context: CallbackContext, previous_results=[]):
    logger.info(f"[randget] {update.message.text}")
    match = re.match(r'/[\S]+\s+([\S]+)', update.message.text)
    search_string = match.group(1) if match else ""
    keys = [key for key in all_keys(search_string) if key not in previous_results]
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
    val = get_val(key)
    again_setter(lambda: handle_randget(update, context, previous_results + [key]))
    await send_val(update.get_bot(), CommandTrigger.from_update(update), key, val, show_header=True)


async def handle_rawget(update: Update, context: CallbackContext):
    logger.info(f"[rawget] {update.message.text}")
    if (match := re.match(r'/[\S]+\s+(.+)', update.message.text)) is None:
        await update.message.reply_text("Ты чего хочешь-то?", do_quote=True)
        return
    if (val := get_close_val(match.group(1).strip())) is None:
        await update.message.reply_text("Не помню такого", do_quote=True)
        return
    if val.type == TYPE_RND:
        await update.message.reply_text(f"/rndset {val.key} {val.data}", do_quote=False)
    else:
        await update.message.reply_text(f"/set {val.key} {fmt_rawget(val.type, val.data, val.caption)}", do_quote=False)


async def handle_rndset(update: Update, context: CallbackContext):
    logger.info(f"[rndset] {update.message.text}")
    if (match := re.match(r'/[\S]+\s+([\S]+)\s+(.+)', update.message.text, re.DOTALL)) is None:
        match = re.match(r'/[\S]+\s+([\S]+)', update.message.text)
        if match and update.message.reply_to_message is not None and update.message.reply_to_message.text is not None:
            key = match.group(1)
            data = update.message.reply_to_message.text
        else:
            await update.message.reply_text("Что-то я ничего не понял. Тебе нужно написать в качестве значения разделенный пробелами список ключей, по которым будет делаться /get. Например /rndset key funnyget1 funnyget2 funnyget3", do_quote=True)
            return
    else:
        key = match.group(1)
        data = match.group(2)
    old = set_val(key, TYPE_RND, data)
    await send_confirm_set_val(update, key, old, False)


async def handle_set(update: Update, context: CallbackContext):
    logger.info(f"[set] {update.message.text}")
    set_as_link = False
    caption = ""
    if (match := re.match(r'/[\S]+\s+([\S]+)\s+(.+)', update.message.text, re.DOTALL)) is None:
        match = re.match(r'/[\S]+\s+([\S]+)', update.message.text)
        if match and update.message.reply_to_message is not None:
            key = match.group(1)
            poll = update.message.reply_to_message.poll
            if poll is not None:
                poll_json = {"question": poll.question, "options": [option.text for option in poll.options],
                             "is_anonymous": poll.is_anonymous, "allows_multiple_answers": poll.allows_multiple_answers}
                type, data = TYPE_POLL, json.dumps(poll_json, ensure_ascii=False)
            elif update.message.reply_to_message.sticker is not None:
                # It's important to note that file_ids are persistent BUT they can't be shared between bots. So it's impossible to fully port the database from one bot to another
                # file_unique_ids are persistent between bots but you can't send or download them so they are useless
                type, data = TYPE_STICKER, update.message.reply_to_message.sticker.file_id
            elif update.message.reply_to_message.animation is not None:
                type, data = TYPE_GIF, update.message.reply_to_message.animation.file_id
                caption = update.message.reply_to_message.caption or ""
            # I don't know why but some GIF animations are only stored in .document but not in .animation even though they behave the same
            # Maybe we can unify this behavior IF all of the animations are stored in document?
            elif update.message.reply_to_message.document is not None and update.message.reply_to_message.document.mime_type == 'image/gif':
                type, data = TYPE_GIF, update.message.reply_to_message.document.file_id
                caption = update.message.reply_to_message.caption or ""
            elif update.message.reply_to_message.photo is not None and len(update.message.reply_to_message.photo) > 0:
                # Messages store photos in an array where the last object of an array is the highest resolution version of a photo
                type, data = TYPE_PHOTO, update.message.reply_to_message.photo[-1].file_id
                caption = update.message.reply_to_message.caption or ""
            elif update.message.reply_to_message.video is not None:
                type, data = TYPE_VIDEO, update.message.reply_to_message.video.file_id
                caption = update.message.reply_to_message.caption or ""
            elif update.message.reply_to_message.voice is not None:
                type, data = TYPE_VOICE, update.message.reply_to_message.voice.file_id
            elif update.message.reply_to_message.text is not None:
                type, data, caption = parse_set_data(update.message.reply_to_message.text)
            elif update.message.reply_to_message.link is not None:
                set_as_link = True
                type, data = TYPE_TEXT, update.message.reply_to_message.link
            else:
                await update.message.reply_text("Что-то я ничего не понял...", do_quote=True)
                return
        else:
            await update.message.reply_text("Что-то я ничего не понял. Удали свой /set и напиши нормально", do_quote=True)
            return
    else:
        key = match.group(1)
        type, data, caption = parse_set_data(match.group(2))
    old = set_val(key, type, data, caption)
    await send_confirm_set_val(update, key, old, set_as_link)


async def send_confirm_set_val(update: Update, key: str, old: db.GetVal | None, set_as_link: bool):
    extra_text = " (ссылкой на сообщение)" if set_as_link else ""
    if old is None:
        await update.message.reply_text(f"Запомнил {key}{extra_text}!", do_quote=False)
        return
    if (label := REPLACE_VAL_LABELS.get(old.type)) is not None:
        await update.message.reply_text(f"Запомнил {key}{extra_text}! Раньше там {label}", do_quote=False)
        return
    output_limit = 100
    if len(old.data) > output_limit:
        await update.message.reply_text(f"Запомнил {key}{extra_text}! Раньше там было \"{old.data[0:output_limit]}...\" и т.д.", do_quote=False)
    else:
        await update.message.reply_text(f"Запомнил {key}{extra_text}! Раньше там было \"{old.data}\"", do_quote=False)


async def handle_del(update: Update, context: CallbackContext):
    logger.info(f"[del] {update.message.text}")
    if (match := re.match(r'/[\S]+\s+([\S]+)', update.message.text)) is None:
        await update.message.reply_text("Не понял, а что удалить-то хочешь?")
        return
    key = match.group(1)
    if not del_val(key):
        await update.message.reply_text(f"Чего-чего? \"{key}\"? Я такого не знаю", do_quote=False)
    else:
        await update.message.reply_text(f"Ок, я удалил ключ \"{key}\"", do_quote=False)


async def handle_getall(update: Update, context: CallbackContext):
    logger.info("[getall]")
    match = re.match(r'/[\S]+\s+([^\s]+)', update.message.text)
    search_string = match.group(1) if match else ""
    keys = sorted(all_keys(search_string))
    if len(keys) > 0:
        header = 'Так вот же все ГЕТЫ:\n\n' if search_string == "" else f'Вот все ГЕТЫ с \"{search_string}\":\n\n'
        response = header + ", ".join(keys)
        # Telegram has a limit of 4096 characters per message and it doesn't split them automatically
        msgs = [response[i:i + 4096] for i in range(0, len(response), 4096)]
        for text in msgs:
            await update.message.reply_text(text, do_quote=False)
    else:
        if search_string != "":
            await update.message.reply_text(f"Не нашел никаких гетов по запросу \"{search_string}\" >.>", do_quote=False)
        else:
            await update.message.reply_text(f"Я пока не знаю никаких гетов... Но ты можешь их добавить командой /set!", do_quote=False)


_tget_poller_task = None


def del_tget(chat_id: int, msg_id: int):
    db.get().execute(f"DELETE FROM {GJ.TABLE} WHERE {GJ.CHAT_ID}=? AND {GJ.MSG_ID}=?",
                     (chat_id, msg_id))
    db.get().commit()


async def handle_tget(update: Update, context: CallbackContext):
    msg = update.effective_message
    if msg is None or msg.text is None or msg.from_user is None or msg.from_user.id in banned_user_ids:
        return
    logger.info(f"[tget] {msg.text}")

    editing_prev_tget = db.get().execute(f"SELECT 1 FROM {GJ.TABLE} WHERE {GJ.CHAT_ID}=? AND {GJ.MSG_ID}=?",
                                         (msg.chat_id, msg.message_id)).fetchone() is not None

    if (match := re.match(r'/[^\s@]+(?:@\S+)?\s+(\d+)\s+(\S+)', msg.text)) is None:
        if editing_prev_tget:
            del_tget(msg.chat_id, msg.message_id)
        else:
            await msg.reply_text("Напиши задержку в минутах и какой гет тебе выдать: /tget 30 dtg", do_quote=True)
        return

    delay_min, key = int(match.group(1)), match.group(2)
    if delay_min == 0:
        if editing_prev_tget:
            del_tget(msg.chat_id, msg.message_id)
        await send_get_response(update.get_bot(), CommandTrigger.from_update(update), key, show_header=True)
        return

    db.get().insert(db.GetJob(msg_id=msg.message_id, chat_id=msg.chat_id, user_id=msg.from_user.id,
                              get_key=key, target_ts=int(time.time()) + delay_min * 60))
    db.get().commit()
    await update.get_bot().set_message_reaction(msg.chat_id, msg.message_id, "👌")


async def send_due_tgets(bot: Bot):
    jobs = db.get().fetch_many(db.GetJob, f"SELECT * FROM {GJ.TABLE} WHERE {GJ.TARGET_TS}<=? ORDER BY {GJ.TARGET_TS}",
                               (int(time.time()),))
    for job in jobs:
        del_tget(job.chat_id, job.msg_id)
        logger.info(f"[tget] Sending timed \"{job.get_key}\" for message {job.msg_id} in chat {job.chat_id}")
        try:
            trigger = CommandTrigger(chat_id=job.chat_id, msg_id=job.msg_id, user_id=job.user_id)
            val = get_close_val(job.get_key)
            key = val.key if val else job.get_key
            timer = fmt_linked_msg_html(f"⏰ {key}", job.msg_id, job.chat_id)
            await bot.send_message(job.chat_id, timer, parse_mode=ParseMode.HTML)
            await send_val(bot, trigger, key, val, show_header=False)
        except Exception:
            logger.exception(f"Failed to send timed \"{job.get_key}\"")


async def tget_poll_loop(bot: Bot):
    while True:
        await asyncio.sleep(25)
        try:
            await send_due_tgets(bot)
        except Exception:
            logger.exception("tget poller iteration failed")


def start_tget_poller(bot: Bot) -> None:
    global _tget_poller_task
    _tget_poller_task = asyncio.create_task(tget_poll_loop(bot))


def subscribe(a: Application, _again_setter):
    a.add_handler(CommandHandler("get", handle_get))
    a.add_handler(CommandHandler("rawget", handle_rawget))
    a.add_handler(CommandHandler("set", handle_set))
    a.add_handler(CommandHandler("rndset", handle_rndset))
    a.add_handler(CommandHandler("getall", handle_getall))
    a.add_handler(CommandHandler(("randget", "rg"), handle_randget))
    a.add_handler(CommandHandler("del", handle_del))
    a.add_handler(CommandHandler("tget", handle_tget))
    global again_setter
    again_setter = _again_setter
