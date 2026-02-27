from telegram import Update
from telegram.ext import Application, CallbackContext, CommandHandler
from telegram.constants import ParseMode
import redis_db
import re
from utils import parse_userid, get_username_by_id
import random
import json
from datetime import datetime, timedelta, time

r = redis_db.connect()
SLAP_STATS_HASH = "slap_stats"
SS_HEALTH = "health"
SS_MADE_ACTION_DATE = "made_action_date"
SS_VULNERABLE_DATE = "vulnerable_date"
SS_TOTAL_SLAPS = "total_slaps"
SS_TOTAL_HEALS = "total_heals"
SS_TOTAL_PARRIES = "total_parries"
SS_TOTAL_PERFECT_PARRIES = "total_perfect_parries"
SS_LAST_SLAPPED_DATE = "last_slapped_date"
SS_LAST_SLAPPED_BY_USERID = "last_slapped_by_userid"

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
DEFAULT_HEALTH = 5


def get_slap_stats(user_id) -> dict:
    stats = r.hget(SLAP_STATS_HASH, str(user_id))
    if stats is None:
        return {}
    json_string = stats
    try:
        return json.loads(json_string)
    except:
        return {}


def is_cooldown_active(cooldown_start_date_str) -> bool:
    if cooldown_start_date_str is None:
        return False
    cur_datetime = datetime.now()

    cooldown_start_date_dt = datetime.strptime(
        cooldown_start_date_str, DATETIME_FORMAT)
    is_same_day = cur_datetime.year == cooldown_start_date_dt.year \
        and cur_datetime.month == cooldown_start_date_dt.month \
        and cur_datetime.day == cooldown_start_date_dt.day
    return is_same_day


async def slap(update: Update, context: CallbackContext):
    stats = get_slap_stats(update.message.from_user.id)
    if is_cooldown_active(stats.get(SS_MADE_ACTION_DATE)):
        await update.message.reply_text(
            "Ты можешь делать только один /slap или /heal за день!", do_quote=True)
        return

    match = re.match(r'/[\S]+\s+(.+)', update.message.text)
    if (match == None):
        if update.message.reply_to_message is not None:
            user_id = update.message.reply_to_message.from_user.id
        else:
            await update.message.reply_text("Кого будем шлепать?", do_quote=False)
            return
    else:
        user_id = parse_userid(match.group(1), context)
    user_not_in_chat = False
    try:
        user_not_in_chat = user_id is not None and (await context.bot.get_chat_member(update.message.chat_id, user_id)).status == 'left'
    except:
        user_not_in_chat = True

    if not user_id:
        await update.message.reply_text(
            f"Кто такой \"{match.group(1)}\"? Что-то я таких не знаю...", do_quote=False)
        return
    elif str(user_id) == str(context.bot.id):
        await update.message.reply_text("🤨", do_quote=True)
    elif (user_not_in_chat):
        await update.message.reply_text("Ты хотел кого-то шлепнуть... но его не оказалось в чате", do_quote=True)
    elif str(user_id) == str(update.message.from_user.id):
        await update.message.reply_text("Хочешь шлепнуть сам себя? Сделай это в реальной жизни", do_quote=True)
    else:
        lucky_roll = random.random() < 0.05
        if not lucky_roll:
            stats[SS_MADE_ACTION_DATE] = datetime.now().strftime(DATETIME_FORMAT)
        stats[SS_TOTAL_SLAPS] = stats.get(SS_TOTAL_SLAPS, 0) + 1
        other_user_stats = get_slap_stats(user_id)
        other_user_stats[SS_HEALTH] = other_user_stats.get(SS_HEALTH, DEFAULT_HEALTH) - 1
        other_user_stats[SS_LAST_SLAPPED_DATE] = datetime.now().strftime(DATETIME_FORMAT)
        other_user_stats[SS_LAST_SLAPPED_BY_USERID] = update.message.from_user.id
        r.hset(SLAP_STATS_HASH, str(update.message.from_user.id), json.dumps(stats))
        r.hset(SLAP_STATS_HASH, str(user_id), json.dumps(other_user_stats))

        append = f"\n\nУДАЧНЫЙ ШЛЕПОК!\n<b>{update.message.from_user.username}</b> может сделать еще одно действие сегодня!" if lucky_roll else ""
        await update.message.reply_text(
            f"<b>{update.message.from_user.username}</b> шлепнул @{get_username_by_id(user_id)} большой рыбой по лицу!{append}", do_quote=False, parse_mode=ParseMode.HTML)


async def heal(update: Update, context: CallbackContext):
    stats = get_slap_stats(update.message.from_user.id)
    if is_cooldown_active(stats.get(SS_MADE_ACTION_DATE)):
        await update.message.reply_text(
            "Ты можешь делать только один /slap или /heal за день!", do_quote=True)
        return

    match = re.match(r'/[\S]+\s+(.+)', update.message.text)
    if (match == None):
        if update.message.reply_to_message is not None:
            user_id = update.message.reply_to_message.from_user.id
        else:
            await update.message.reply_text("Кого будем лечить?", do_quote=False)
            return
    else:
        user_id = parse_userid(match.group(1), context)
    user_not_in_chat = False
    try:
        user_not_in_chat = user_id is not None and (await context.bot.get_chat_member(update.message.chat_id, user_id)).status == 'left'
    except:
        user_not_in_chat = True

    if not user_id:
        await update.message.reply_text(
            f"Кто такой \"{match.group(1)}\"? Что-то я таких не знаю...", do_quote=False)
        return
    elif str(user_id) == str(context.bot.id):
        await update.message.reply_text("Спасибо, но я вне игры :^", do_quote=True)
    elif (user_not_in_chat):
        await update.message.reply_text("Ты хотел кого-то полечить... но его не оказалось в чате", do_quote=True)
    elif str(user_id) == str(update.message.from_user.id):
        await update.message.reply_text("Ты не можешь лечить сам себя!", do_quote=True)
    else:
        lucky_roll = random.random() < 0.05
        if not lucky_roll:
            stats[SS_MADE_ACTION_DATE] = datetime.now().strftime(DATETIME_FORMAT)
        stats[SS_TOTAL_HEALS] = stats.get(SS_TOTAL_HEALS, 0) + 1
        other_user_stats = get_slap_stats(user_id)
        other_user_stats[SS_HEALTH] = other_user_stats.get(SS_HEALTH, DEFAULT_HEALTH) + 1
        append = f"\n\nУДАЧНОЕ ЛЕЧЕНИЕ!\n<b>{update.message.from_user.username}</b> может сделать еще одно действие сегодня!" if lucky_roll else ""
        if is_cooldown_active(other_user_stats.get(SS_VULNERABLE_DATE)):
            other_user_stats.pop(SS_VULNERABLE_DATE, None)
            await update.message.reply_text(f"<b>{update.message.from_user.username}</b> погладил @{get_username_by_id(user_id)} по голове и снял уязвимость!{append}", do_quote=False, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(f"<b>{update.message.from_user.username}</b> погладил @{get_username_by_id(user_id)} по голове.{append}", do_quote=False, parse_mode=ParseMode.HTML)

        r.hset(SLAP_STATS_HASH, str(update.message.from_user.id), json.dumps(stats))
        r.hset(SLAP_STATS_HASH, str(user_id), json.dumps(other_user_stats))
        

async def parry(update: Update, context: CallbackContext):
    stats = get_slap_stats(update.message.from_user.id)
    if is_cooldown_active(stats.get(SS_VULNERABLE_DATE)):
        await update.message.reply_text("Ты уязвим и не можешь парировать", do_quote=True)
        return

    last_slapped_date_str = stats.get(SS_LAST_SLAPPED_DATE)
    if last_slapped_date_str is None:
        await update.message.reply_text("Некого парировать", do_quote=True)
        return
    
    last_slapped_date = datetime.strptime(last_slapped_date_str, DATETIME_FORMAT)
    seconds_diff = (datetime.now() - last_slapped_date).total_seconds()
    if (seconds_diff <= 8):
        stats[SS_TOTAL_PERFECT_PARRIES] = stats.get(SS_TOTAL_PERFECT_PARRIES, 0) + 1
        stats[SS_HEALTH] = stats.get(SS_HEALTH, DEFAULT_HEALTH) + 1
        other_user_id = stats.get(SS_LAST_SLAPPED_BY_USERID, -1)
        other_user_stats = get_slap_stats(other_user_id)
        other_user_stats[SS_HEALTH] = other_user_stats.get(SS_HEALTH, DEFAULT_HEALTH) - 1
        other_user_stats[SS_TOTAL_SLAPS] = other_user_stats.get(SS_TOTAL_SLAPS, 0) - 1
        other_user_stats[SS_VULNERABLE_DATE] = datetime.now().strftime(DATETIME_FORMAT)
        await update.message.reply_text(f"ИДЕАЛЬНОЕ ПАРИРОВАНИЕ! <b>{update.message.from_user.username}</b> спарировал шлепок от @{get_username_by_id(other_user_id)} и сделал его уязвимым на день!", do_quote=False, parse_mode=ParseMode.HTML)
        stats.pop(SS_LAST_SLAPPED_DATE, None)
        stats.pop(SS_LAST_SLAPPED_BY_USERID, None)
        r.hset(SLAP_STATS_HASH, str(update.message.from_user.id), json.dumps(stats))
        r.hset(SLAP_STATS_HASH, str(other_user_id), json.dumps(other_user_stats))
    elif (seconds_diff <= 63):
        stats[SS_TOTAL_PARRIES] = stats.get(SS_TOTAL_PARRIES, 0) + 1
        stats[SS_HEALTH] = stats.get(SS_HEALTH, DEFAULT_HEALTH) + 1
        other_user_id = stats.get(SS_LAST_SLAPPED_BY_USERID, -1)
        other_user_stats = get_slap_stats(other_user_id)
        other_user_stats[SS_TOTAL_SLAPS] = other_user_stats.get(SS_TOTAL_SLAPS, 0) - 1
        await update.message.reply_text(f"<b>{update.message.from_user.username}</b> спарировал шлепок от @{get_username_by_id(other_user_id)}!", do_quote=False, parse_mode=ParseMode.HTML)
        stats.pop(SS_LAST_SLAPPED_DATE, None)
        stats.pop(SS_LAST_SLAPPED_BY_USERID, None)
        r.hset(SLAP_STATS_HASH, str(update.message.from_user.id), json.dumps(stats))
        r.hset(SLAP_STATS_HASH, str(other_user_id), json.dumps(other_user_stats))
    else:
        await update.message.reply_text("Парирование провалено", do_quote=True)
        stats.pop(SS_LAST_SLAPPED_DATE, None)
        stats.pop(SS_LAST_SLAPPED_BY_USERID, None)
        r.hset(SLAP_STATS_HASH, str(update.message.from_user.id), json.dumps(stats))


async def slap_stats(update: Update, context: CallbackContext):
    slappers_dict = {}
    for key in r.hgetall(SLAP_STATS_HASH):
        username = get_username_by_id(key)
        slappers_dict[username] = get_slap_stats(key)
                
    if len(slappers_dict.keys()) == 0:
        await update.message.reply_text("Пока что никто никого не шлепал, поэтому и статистики нет", do_quote=False)
        return
    message = f"Вот статистика шлепунов.\nИгрок [Шлеп-счет]  (Успешные шлепки / Лечения / Парирования / Идеальные парирования)\n\n"
    i = 1
    for k, v in dict(sorted(slappers_dict.items(), key=lambda item: (item[1].get(SS_HEALTH, DEFAULT_HEALTH), item[1].get(SS_TOTAL_SLAPS, 0), item[1].get(SS_TOTAL_HEALS, 0), item[1].get(SS_TOTAL_PARRIES, 0), item[1].get(SS_TOTAL_PERFECT_PARRIES, 0)), reverse=True)).items():
        username_markdown = k
        username_markdown = f"<b>{username_markdown}</b>" if is_cooldown_active(v.get(SS_VULNERABLE_DATE)) else username_markdown
        username_markdown = f"<i>{username_markdown}</i>" if is_cooldown_active(v.get(SS_MADE_ACTION_DATE)) else username_markdown
        message += f"{i}. {username_markdown} [{v.get(SS_HEALTH, DEFAULT_HEALTH)}]  ({v.get(SS_TOTAL_SLAPS, 0)}/{v.get(SS_TOTAL_HEALS, 0)}/{v.get(SS_TOTAL_PARRIES, 0)}/{v.get(SS_TOTAL_PERFECT_PARRIES, 0)})\n"
        i += 1


    tomorrow = datetime.now() + timedelta(days=1)
    time_to_next = datetime.combine(tomorrow, time.min) - datetime.now()
    time_to_next_h, time_to_next_m = time_to_next.seconds // 3600, (time_to_next.seconds // 60) % 60
    message += f"Новые шлепки будут доступны через {time_to_next_h} ч. и {time_to_next_m} м."
    await update.message.reply_text(f"{message}", do_quote=False, parse_mode=ParseMode.HTML)


async def slap_rules(update: Update, context: CallbackContext):
    rules = "Правила /slap игры.\n" + \
            "Ты можешь шлепнуть любого игрока, отправив /slap и указав другого игрока (по его username или кастомному никнейму). Это снизит его шлеп-счет на 1.\n" + \
            "Когда игрока шлепнули, он может отправить /parry чтобы заблокировать шлепок. Если /parry был отправлен в течение минуты после последнего шлепка, эта атака будет успешно заблокирована и игрок не получит урона.\n" + \
            "Однако если /parry был отправлен очень быстро, а именно в течение 8 секунд после последнего шлепка, то произойдет идеальное парирование, которое заблокирует атаку, нанесет противнику 1 урон и сделает его уязвимым на день. Уязвимые игроки не могут парировать шлепки.\n" + \
            "Вместо шлепка ты можешь полечить кого-нибудь, отправив /heal и указав другого игрока. Это увеличит его шлеп-счет на 1, а также снимет уязвимость.\n" + \
            "За день ты можешь делать только один шлепок или лечение, но сколько угодно парирований.\n" + \
            "Отправь /slapstats, чтобы посмотреть общую статистику по игре."
    await update.message.reply_text(rules, do_quote=False)


async def reset_my_slap(update: Update, context: CallbackContext):
    stats = get_slap_stats(update.message.from_user.id)
    stats.pop(SS_MADE_ACTION_DATE, None)
    r.hset(SLAP_STATS_HASH, str(update.message.from_user.id), json.dumps(stats))
    await update.message.reply_text("You can now /slap again. This is a debug command that should be removed on prod", do_quote=False)


def subscribe(a: Application):
    a.add_handler(CommandHandler("slap", slap))
    a.add_handler(CommandHandler("heal", heal))
    a.add_handler(CommandHandler("parry", parry))
    a.add_handler(CommandHandler("slapstats", slap_stats))
    a.add_handler(CommandHandler("slaprules", slap_rules))
    a.add_handler(CommandHandler("resetmyslap", reset_my_slap))
    pass
