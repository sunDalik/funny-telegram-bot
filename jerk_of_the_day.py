from telegram import ParseMode, Update
from telegram.ext import Updater, CommandHandler
from _secrets import jerk_aliases
import random
import redis_db
from utils import in_whitelist
from datetime import datetime, timedelta, time
import logging
from time import sleep

logger = logging.getLogger(__name__)
r = redis_db.connect()

JERKS_REG_SET = 'jerks_reg'
JERKS = 'jerks'
JERKS_META = 'jerks_meta'


def get_daily_jerk_word() -> list:
    curr_date = datetime.now()
    seed = int(str(curr_date.year % 100) + str(curr_date.month) + str(curr_date.day))
    my_random = random.Random()
    my_random.seed(seed)
    return my_random.choice(jerk_aliases)


def jerk_reg(update: Update, context):
    if not in_whitelist(update):
        return
    # set user id to regs
    logger.info('[jerk_reg]')
    reg_user_id = update.message.from_user.id
    reg_user_name = update.message.from_user.username
    already_register = r.sismember(JERKS_REG_SET, reg_user_id)
    count = r.scard(JERKS_REG_SET)
    redis_db.update_user_data(reg_user_id, reg_user_name)
    if already_register:
        update.message.reply_text(f"@{reg_user_name}, ты уже участник этой клоунады", quote=False)
        return
    # set user id and username
    r.sadd(JERKS_REG_SET, reg_user_id)
    update.message.reply_text(f"@{reg_user_name}, теперь ты участвуешь в лотерее вместе с {count} другими {get_daily_jerk_word()[3]}", quote=False)


def jerk_unreg(update: Update, context):
    if not in_whitelist(update):
        return
    logger.info('[jerk_unreg]')
    reg_user_id = update.message.from_user.id
    reg_user_name = update.message.from_user.username
    already_register = r.sismember(JERKS_REG_SET, reg_user_id)
    if not already_register:
        update.message.reply_text(f"@{reg_user_name}, ты и так не регистрировался", quote=False)
        return
    r.srem(JERKS_REG_SET, reg_user_id)
    update.message.reply_text(f"Правильное решение, @{reg_user_name}. Вычеркнул тебя из списка", quote=False)


def jerk_roll(update: Update, context):
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
            cur_jerk_username = redis_db.get_username_by_id(cur_jerk_id)
            tomorrow = cur_datetime + timedelta(days=1)
            time_to_next = datetime.combine(tomorrow, time.min) - cur_datetime
            time_to_next_h, time_to_next_m = time_to_next.seconds // 3600, (time_to_next.seconds // 60) % 60
            update.message.reply_text(f"Сегодняшний {get_daily_jerk_word()[0]} дня: <b>{cur_jerk_username}</b>.\n"
                                      f"Следующий запуск будет доступен через: "
                                      f"{time_to_next_h} ч. и {time_to_next_m} м.",
                                      quote=False, parse_mode=ParseMode.HTML)
            return
    players = r.smembers(JERKS_REG_SET)
    pl = [player.decode('utf-8') for player in players]
    if (len(pl) == 0):
        update.message.reply_text("А че вы роллить собрались? Никто не зарегистрировался", quote=True)
    winner_id = random.choice(pl)
    winner_username = redis_db.get_username_by_id(winner_id)
    r.hset(JERKS_META, 'last_jerk', winner_id)
    r.hset(JERKS_META, 'roll_time', cur_datetime_str)
    r.hincrby(JERKS, winner_id, 1)

    update.message.reply_text(f"Выбираю {get_daily_jerk_word()[1]} на сегодня", quote=False)
    sleep(1)
    update.message.reply_text(f"А вот и победитель - @{winner_username}!", quote=False)
    logger.info(f'  WINNER for {cur_datetime_str} is {winner_id}: {winner_username}')
    return


def get_jerk_stats(update: Update, context):
    if (not in_whitelist(update)):
        return
    jerks_dict = {}
    for key in r.hgetall(JERKS):
        winner_username = redis_db.get_username_by_id(key.decode("utf-8"))
        jerks_dict[winner_username] = r.hget(JERKS, key)
    message = f"Вот статистика {get_daily_jerk_word()[2]}:\n"
    i = 1
    for k, v in dict(sorted(jerks_dict.items(), key=lambda item: item[1], reverse=True)).items():
        message += f"{i}. {k} - {v.decode('utf-8')}\n"
        i += 1
    update.message.reply_text(f"{message}", quote=False)


def get_jerk_regs(update: Update, context):
    if (not in_whitelist(update)):
        return
    players = [player.decode('utf-8') for player in r.smembers(JERKS_REG_SET)]
    if (len(players) == 0):
        update.message.reply_text(f"Никто не зарегистрировался на {get_daily_jerk_word()[1]} дня...", quote=False)    
        return
    message = "Вот все известные мне персонажи:\n"
    i = 1
    for player in players:
        message += f"{i}. {redis_db.get_username_by_id(player)}\n"
        i += 1
    update.message.reply_text(f"{message}", quote=False)


def subscribe(u: Updater):
    u.dispatcher.add_handler(CommandHandler("reg", jerk_reg))
    u.dispatcher.add_handler(CommandHandler("unreg", jerk_unreg))
    u.dispatcher.add_handler(CommandHandler("jerk", jerk_roll))
    u.dispatcher.add_handler(CommandHandler("jerkstats", get_jerk_stats))
    u.dispatcher.add_handler(CommandHandler("jerkall", get_jerk_regs))
    pass