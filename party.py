from telegram import ParseMode, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler
import redis_db
from utils import in_whitelist
from datetime import datetime, timedelta, time
import logging
import re
import json
from typing import Optional

logger = logging.getLogger(__name__)
r = redis_db.connect()

PARTIES = 'party'
REQUIRED_PEOPLE_COUNT = "required_people_count"
CUR_PEOPLE_JOINED = "cur_people_joined"
NOTIFICATIONS_RECEIVERS = "notifications_receivers"
LAST_TOUCHED_DATETIME = "last_touched_date"
MAX_PEOPLE_IN_PARTY = 10

def party_create(update: Update, context):
    if not in_whitelist(update):
        return
    logger.info('[party_create]')

    match = re.match(r'/[\S]+\s+(.+)\s+([0-9]+)', update.message.text)
    if (match == None):
        update.message.reply_text("Дедушка тебя не понимает", quote=False)
        return
    else:
        game_name = match.group(1)
        people_count = int(match.group(2))
        if (people_count == 0):
            update.message.reply_text("Приколист дохуя?", quote=False)
            return
        if (people_count > MAX_PEOPLE_IN_PARTY):
            update.message.reply_text("Зачем столько людей? Поставь нормальное число", quote=False)
            return

    logger.info(f'[party_create] {game_name} {people_count}')

    new_party = {REQUIRED_PEOPLE_COUNT: people_count, CUR_PEOPLE_JOINED: [], NOTIFICATIONS_RECEIVERS: [], LAST_TOUCHED_DATETIME: None}


    already_exists = r.hexists(PARTIES, game_name)
    if already_exists:
        update.message.reply_text("Такая пати уже есть", quote=False)
        return

    save_party(game_name, new_party)
    update.message.reply_text(f"Команда для игры в {game_name} создана.\nЖду, пока наберется {people_count} человек и пингую", quote=False)

def party_list(update: Update, context):
    if not in_whitelist(update):
        return
    logger.info('[party_list]')

    parties = r.hgetall(PARTIES)
    if len(parties.keys()) == 0:
        update.message.reply_text("Пати нет... Но ты можешь их создать командой /partycreate!", quote=False)
        return
    reply_text = "Список всех пати\n"
    for game_name, party_json in parties.items():
        party = json.loads(party_json)
        party = daily_party_reset_if_needed(game_name, party)
        cur_people_count = len(party[CUR_PEOPLE_JOINED])
        required_people_count = party[REQUIRED_PEOPLE_COUNT]
        reply_text = reply_text + f"{game_name} - {cur_people_count}/{required_people_count}"
        reply_text = reply_text + "\n"

    update.message.reply_text(reply_text, quote=False)

def party_join(update: Update, context):
    if not in_whitelist(update):
        return
    logger.info('[party_join]')

    game_name = get_game_name_from_msg_if_exists_or_send_error_reply(update)
    if (game_name == None):
        return

    logger.info(f'[party_join] {game_name}')
    username = update.message.from_user.username
    join_party(game_name, username, update, True)


def party_delete(update: Update, context):
    if not in_whitelist(update):
        return
    logger.info('[party_delete]')

    game_name = get_game_name_from_msg_if_exists_or_send_error_reply(update)
    if (game_name == None):
        return

    logger.info(f'[party_delete] {game_name}')

    party_json = r.hdel(PARTIES, game_name)
    update.message.reply_text(f"Пати для {game_name} удалена... Довольны?", quote=False)

def party_ping_unregister(update: Update, context):
    if not in_whitelist(update):
        return
    logger.info('[party_ping_unregister]')

    game_name = get_game_name_from_msg_if_exists_or_send_error_reply(update)
    if (game_name == None):
        return

    logger.info(f'[party_ping_unregister] {game_name}')

    party = load_party(game_name)
    party = daily_party_reset_if_needed(game_name, party)
    username = update.message.from_user.username
    if username not in party[NOTIFICATIONS_RECEIVERS]:
        update.message.reply_text(f"Ты и так не получаешь уведомления {game_name} пати", quote=False)
        return
    else:
        party[NOTIFICATIONS_RECEIVERS].remove(username)


    save_party(game_name, party)
    update.message.reply_text(f"Ты больше не будешь получать нотификации о пати для {game_name}... Пока снова не зайдешь в пати", quote=False)

def party_leave(update: Update, context):
    if not in_whitelist(update):
        return
    logger.info('[party_leave]')

    game_name = get_game_name_from_msg_if_exists_or_send_error_reply(update)
    if (game_name == None):
        return

    logger.info(f'[party_leave] {game_name}')

    party = load_party(game_name)
    party = daily_party_reset_if_needed(game_name, party)
    username = update.message.from_user.username
    if username not in party[CUR_PEOPLE_JOINED]:
        update.message.reply_text(f"Ты и так не в пати", quote=False)
        return
    else:
        party[CUR_PEOPLE_JOINED].remove(username)


    save_party(game_name, party)
    cur_people_joined_count = len(party[CUR_PEOPLE_JOINED])
    required_people_count = party[REQUIRED_PEOPLE_COUNT]
    update.message.reply_text(f"Ты ливнул из пати для {game_name}...\nТеперь в пати {cur_people_joined_count}/{required_people_count} челов", quote=False)

# Can be combined somehow with party_ping_all but I am too lazy
def party_ping(update: Update, context):
    if not in_whitelist(update):
        return
    logger.info('[party_ping]')

    game_name = get_game_name_from_msg_if_exists_or_send_error_reply(update)
    if (game_name == None):
        return

    logger.info(f'[party_ping] {game_name}')

    party = load_party(game_name)
    party = daily_party_reset_if_needed(game_name, party)
    cur_people_joined = party[CUR_PEOPLE_JOINED]
    notifications_receivers = party[NOTIFICATIONS_RECEIVERS]
    regular_players_that_are_not_joined = list(set(notifications_receivers) - set(cur_people_joined))
    reply_text = f"Пингую всех, кто когда либо был в {game_name} пати, но сейчас не джойнут\n"
    for username in regular_players_that_are_not_joined:
        reply_text = reply_text + f"@{username} "
    reply_text = reply_text + f"\n\nЕсли ты не хочешь быть в этом списке, юзай /partypingunregister"

    update.message.reply_text(reply_text, quote=False)

def party_info(update: Update, context):
    if not in_whitelist(update):
        return
    logger.info('[party_info]')

    game_name = get_game_name_from_msg_if_exists_or_send_error_reply(update)
    if (game_name == None):
        return

    logger.info(f'[party_info] {game_name}')

    party = load_party(game_name)
    logger.info(party)
    party = daily_party_reset_if_needed(game_name, party)
    cur_people_joined = party[CUR_PEOPLE_JOINED]
    cur_people_joined_count = len(party[CUR_PEOPLE_JOINED])
    required_people_count = party[REQUIRED_PEOPLE_COUNT]
    notifications_receivers = party[NOTIFICATIONS_RECEIVERS]

    reply_text = f"Инфа по пати на {game_name}:\n"
    reply_text = reply_text + f"{cur_people_joined_count}/{required_people_count} челов хотят сегодня зарубить\n"

    if cur_people_joined_count != 0:
        reply_text = reply_text + f"А именно: "
        for username in cur_people_joined:
            reply_text = reply_text + f"{username} "
        reply_text = reply_text + "\n"
    
    if len(notifications_receivers) != 0:
        regular_players_that_are_not_joined = list(set(notifications_receivers) - set(cur_people_joined))
        if len(regular_players_that_are_not_joined) > 0:
            reply_text = reply_text + f"Раньше играли, а щас отлынивают: "
            for username in regular_players_that_are_not_joined:
                reply_text = reply_text + f"{username} "
            reply_text = reply_text + "\n"

    update.message.reply_text(reply_text, quote=False)


# Can be combined somehow with party_ping but I am too lazy
def party_ping_all(update: Update, context):
    if not in_whitelist(update):
        return
    logger.info('[party_ping]')

    game_name = get_game_name_from_msg_if_exists_or_send_error_reply(update)
    if (game_name == None):
        return

    logger.info(f'[party_ping] {game_name}')

    party = load_party(game_name)
    party = daily_party_reset_if_needed(game_name, party)
    username = update.message.from_user.username
    reply_text = f"Пингую всех, кто когда либо был в {game_name} пати.\n"
    for username in party[NOTIFICATIONS_RECEIVERS]:
        reply_text = reply_text + f"@{username} "
    reply_text = reply_text + f"\n\nЕсли ты не хочешь быть в этом списке, юзай /partypingunregister"

    update.message.reply_text(reply_text, quote=False)

def on_join_button_press(update: Update, ctx):
    query = update.callback_query
    # Not checking for whitelist because its broken with callback query...
    
    args = query.data.split()
    game_name = args[1]
    if not r.hexists(PARTIES, game_name):
        query.answer()
        return
    
    query.answer(f"Добавил тебя в пати {game_name}")
    join_party(game_name, query.from_user.username, update, False)
    



# Ideally there needs to be 1 common handler for all commands that incapsulates parsing message, whitelisting, daily reset
#  and other non-command-related stuff.
def subscribe(u: Updater):
    u.dispatcher.add_handler(CommandHandler("partycreate", party_create))
    u.dispatcher.add_handler(CommandHandler("partylist", party_list))
    u.dispatcher.add_handler(CommandHandler("party", party_join))
    u.dispatcher.add_handler(CommandHandler("partydelete", party_delete)) #not tested
    u.dispatcher.add_handler(CommandHandler("partypingunregister", party_ping_unregister)) #not tested
    u.dispatcher.add_handler(CommandHandler("partyleave", party_leave)) #not tested
    u.dispatcher.add_handler(CommandHandler("partyping", party_ping)) #not tested
    u.dispatcher.add_handler(CommandHandler("partypingall", party_ping_all)) #not tested
    u.dispatcher.add_handler(CommandHandler("partyinfo", party_info)) #not tested
    u.dispatcher.add_handler(CallbackQueryHandler(on_join_button_press, pattern="^join_party"))
    pass


# ----------------- Helpers functions for readability ---------------
def get_game_name_from_msg_if_exists_or_send_error_reply(update: Update) -> Optional[str]:
    match = re.match(r'/[\S]+\s+(.+)', update.message.text)
    if (match == None):
        update.message.reply_text("Не понял", quote=False)
        return None
    else:
        game_name = match.group(1)

    if not r.hexists(PARTIES, game_name):
        update.message.reply_text("Нет такой пати", quote=False)
        return None

    return game_name

def load_party(game_name: str):
    party_json = r.hget(PARTIES, game_name)
    party = json.loads(party_json)
    return party

def save_party(game_name: str, party):
    r.hset(PARTIES, game_name, json.dumps(party))

# Should be used alongside load_party(). Party should be reset every day, so we check if party was last touched yesterday, 
# then reset it and update touch
def daily_party_reset_if_needed(game_name: str, party):
    last_touched = party[LAST_TOUCHED_DATETIME]

    datetime_format = '%Y-%m-%d %H:%M:%S'
    cur_datetime = datetime.now()
    cur_datetime_str = cur_datetime.strftime(datetime_format)

    if (last_touched == None):
        # should be changed to inner function
        party[LAST_TOUCHED_DATETIME] = cur_datetime_str
        party[CUR_PEOPLE_JOINED] = []
        save_party(game_name, party)
        return party

    last_touched_dt = datetime.strptime(last_touched, datetime_format)
    is_same_day = cur_datetime.year == last_touched_dt.year and cur_datetime.month == last_touched_dt.month \
                      and cur_datetime.day == last_touched_dt.day
    if not is_same_day:
        # should be changed to inner function
        party[LAST_TOUCHED_DATETIME] = cur_datetime_str
        party[CUR_PEOPLE_JOINED] = []
        save_party(game_name, party)
        return party

    return party

def add_join_button(game_name: str):
    keyboard = [[
                InlineKeyboardButton(text="Я тоже хочу!",
                                          callback_data=f"join_party {game_name}")
    ]]
    markup = InlineKeyboardMarkup(keyboard)
    return markup

def join_party(game_name: str, username: str, update: Update, send_reply: bool):
    party = load_party(game_name)
    party = daily_party_reset_if_needed(game_name, party)
    required_people_count = party[REQUIRED_PEOPLE_COUNT]
    username = username

    if username not in party[CUR_PEOPLE_JOINED]:
        party[CUR_PEOPLE_JOINED].append(username)
    else:
        if send_reply:
            update.message.reply_text("Ты уже в пати", quote=False)
        return

    if username not in party[NOTIFICATIONS_RECEIVERS]:
        party[NOTIFICATIONS_RECEIVERS].append(username)

    save_party(game_name, party)
    cur_people_count = len(party[CUR_PEOPLE_JOINED])

    if (required_people_count == cur_people_count):
        party_ready_reply_text = f"Пати для {game_name} набралась!\n"
        for joined_user_username in party[CUR_PEOPLE_JOINED]:
            party_ready_reply_text = party_ready_reply_text + f"@{joined_user_username} "
        update.message.reply_text(party_ready_reply_text, quote=False)
        return
    
    if not send_reply:
        return
    
    if (required_people_count < cur_people_count):
        update.message.reply_text(f"Людей уже больше чем нужно! Жесть", quote=False)
        return

    if (required_people_count > cur_people_count):
        update.message.reply_text(f"Ты зашел в пати!\nЖдем еще {required_people_count - cur_people_count} челов", quote=False, reply_markup = add_join_button(game_name))
        return

