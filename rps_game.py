from _secrets import user_aliases
from telegram import ParseMode, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
import redis_db
import re
from utils import in_whitelist, parse_userid
import random
import json
from datetime import datetime, timedelta, time
import math

r = redis_db.connect()

games_data = []
MAX_ROUNDS = 5


def format_playing_field(game_state) -> str:
    text = "" 
    if game_state['over']:
        text = "Игра окончена!\n\n"
    elif game_state['current_round'] == 1:
        text = f"Игра началась! Игроки, выберите свой символ\nРаунд {game_state['current_round']} из {MAX_ROUNDS}\n\n"
    else:
        text = f"Раунд {game_state['current_round']} из {MAX_ROUNDS}\n\n"

    emojis = ["🤔", "🤔"]
    if game_state["over"]:
        if game_state["scores"][0] == game_state["scores"][1]:
            emojis = ["🤝", "🤝"]
        elif game_state["scores"][0] > game_state["scores"][1]:
            emojis = ["🎉", "💀"]
        else:
            emojis = ["💀", "🎉"]
    else:
        for i in range(0, 2):
            if game_state["decisions"][i] != "":
                emojis[i] = "✅"
    text += f"{emojis[0]} @{game_state['player_usernames'][0]} ({game_state['scores'][0]})  vs.  {emojis[1]} @{game_state['player_usernames'][1]} ({game_state['scores'][1]})\n\n"
    if game_state['log'] != "":
        text += f"Ход игры:\n{game_state['log']}"
    return text


def clean_old_games():
    global games_data
    MAX_GAMES = 20
    remove_games = max(0, len(games_data) - MAX_GAMES)
    games_data = games_data[remove_games:]


def start_rps(update: Update, context: CallbackContext):
    if (not in_whitelist(update)):
        return
    match = re.match(r'/[\S]+\s+(.+)', update.message.text)
    if (match == None):
        if update.message.reply_to_message is not None:
            user_id = update.message.reply_to_message.from_user.id
        else:
            update.message.reply_text("С кем хочешь сыграть в камень-ножницы-бумага?", quote=False)
            return
    else:
        user_id = parse_userid(match.group(1), context)

    if user_id is None:
        update.message.reply_text(
            f"Кто такой \"{match.group(1)}\"? Что-то я таких не знаю...", quote=False)
        return
    elif str(user_id) == str(update.message.from_user.id):
        update.message.reply_text("Одиноко? Можешь поиграть со мной!", quote=True)
        return
    
    keyboard = [
        [
            InlineKeyboardButton("👊 Камень", callback_data="rps_r"),
            InlineKeyboardButton("🔪 Ножницы", callback_data="rps_s"),
            InlineKeyboardButton("📜 Бумага", callback_data="rps_p"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    username_1 = redis_db.get_username_by_id(update.message.from_user.id)
    # Hack... should be included in the get username function maybe?
    username_2 = context.bot.username if int(user_id) == context.bot.id else redis_db.get_username_by_id(user_id)
    new_game_state = {"message_id": "", "player_ids": [update.message.from_user.id, int(user_id)], "player_usernames": [username_1, username_2], "decisions": ["", ""], "current_round": 1, "scores": [0, 0], "log": "", "over": False}
    message = update.message.reply_text(f"{format_playing_field(new_game_state)}", reply_markup=reply_markup, quote=False)
    new_game_state["message_id"] = str(message.chat_id) + "/" + str(message.message_id)
    games_data.append(new_game_state)
    clean_old_games()


def get_decision_emoji(symbol: str) -> str:
    if symbol == "r":
        return "👊"
    if symbol == "s":
        return "🔪"
    if symbol == "p":
        return "📜"
    return "??"


def on_rps_action(update: Update, context: CallbackContext):
    query = update.callback_query
    # Not checking for whitelist because its broken with callback query...
    # But we still check if the message from query exists in our database so all is good!
    if query.data != "rps_r" and query.data != "rps_s" and query.data != "rps_p":
        return    

    game_state = None
    for state in games_data:
        if state["message_id"] == str(query.message.chat_id) + "/" + str(query.message.message_id):
            game_state = state
            
    if game_state is None:
        query.message.reply_text("Не могу найти игру, вероятно она сильно устарела :(", quote=False)
        query.answer()
        return
    
    player_index = -1
    for i in range(0, 2):
        if query.from_user.id  == game_state["player_ids"][i]:
            player_index = i
            break

    if player_index < 0 or game_state["over"]:
        query.answer()
        return

    if (query.data == "rps_r"):
        game_state["decisions"][player_index] = "r"
    elif (query.data == "rps_p"):
        game_state["decisions"][player_index] = "p"
    elif (query.data == "rps_s"):
        game_state["decisions"][player_index] = "s"

    if game_state["player_ids"][1] == context.bot.id:
        game_state["decisions"][1] = random.choice(["s", "r", "p"])

    if game_state["decisions"][0] != "" and game_state["decisions"][1] != "":
        if game_state["decisions"][0] == game_state["decisions"][1]:
            pass
        elif game_state["decisions"][0] == "r" and game_state["decisions"][1] == "s":
            game_state["scores"][0] += 1
        elif game_state["decisions"][0] == "r" and game_state["decisions"][1] == "p":
            game_state["scores"][1] += 1
        elif game_state["decisions"][0] == "s" and game_state["decisions"][1] == "p":
            game_state["scores"][0] += 1
        elif game_state["decisions"][0] == "s" and game_state["decisions"][1] == "r":
            game_state["scores"][1] += 1
        elif game_state["decisions"][0] == "p" and game_state["decisions"][1] == "r":
            game_state["scores"][0] += 1
        elif game_state["decisions"][0] == "p" and game_state["decisions"][1] == "s":
            game_state["scores"][1] += 1


        game_state["log"] += f"{get_decision_emoji(game_state['decisions'][0])}  x  {get_decision_emoji(game_state['decisions'][1])}\n"
        game_state["decisions"] = ["", ""]       

        if game_state["current_round"] >= MAX_ROUNDS or abs(game_state["scores"][0] - game_state["scores"][1]) > MAX_ROUNDS - game_state["current_round"]:
            game_state["over"] = True
        else:
            game_state["current_round"] += 1 

    query.answer()
    if game_state["over"]:
        query.edit_message_text(text=format_playing_field(game_state))
    else:
        query.edit_message_text(text=format_playing_field(game_state), reply_markup=query.message.reply_markup)


def subscribe(u: Updater):
    u.dispatcher.add_handler(CommandHandler("rps", start_rps))
    u.dispatcher.add_handler(CallbackQueryHandler(on_rps_action))