from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackContext, CommandHandler, CallbackQueryHandler
from telegram.error import RetryAfter
import redis_db
import re
from utils import parse_userid, get_username_by_id
import random
import json
import logging

logger = logging.getLogger(__name__)
r = redis_db.connect()

games_data = []

def format_playing_field(game_state) -> str:
    if game_state['player_ids'][1] is None:
        return f"@{game_state['player_usernames'][0]} ожидает второго игрока в \"Четыре в ряд\"..."
    text = "" 
    if game_state['winner'] is not None:
        text = "Игра окончена!\n\n"

    emojis = ["", ""]
    if game_state["winner"] is not None:
        if game_state["winner"] == 0:
            emojis = ["🎉", "💀"]
        elif game_state["winner"] == 1:
            emojis = ["💀", "🎉"]
        else:
            emojis = ["🤝", "🤝"]
    else:
        for i in range(0, 2):
            if game_state["current_turn"] == i:
                emojis[i] = "🤔"
    text += f"{emojis[0]} @{game_state['player_usernames'][0]} ({get_cell_emoji(0)})  vs.  {emojis[1]} @{game_state['player_usernames'][1]} ({get_cell_emoji(1)})\n\n"
    for row in game_state['board']:
        for col in row:
            text += get_cell_emoji(col)
        text += "\n"
    if game_state["winner"] is None:
        text += f"1⃣2⃣3⃣4⃣5⃣6⃣7⃣"
    return text


def clean_old_games():
    global games_data
    MAX_GAMES = 10
    remove_games = max(0, len(games_data) - MAX_GAMES)
    games_data = games_data[remove_games:]


def get_cf_keyboard(pregame: bool = False) -> InlineKeyboardMarkup:
    if pregame:
        keyboard = [
            [InlineKeyboardButton("Присоединиться к игре", callback_data="cf_join")]
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton("1", callback_data="cf_1"),
                InlineKeyboardButton("2", callback_data="cf_2"),
                InlineKeyboardButton("3", callback_data="cf_3"),
                InlineKeyboardButton("4", callback_data="cf_4"),
                InlineKeyboardButton("5", callback_data="cf_5"),
                InlineKeyboardButton("6", callback_data="cf_6"),
                InlineKeyboardButton("7", callback_data="cf_7"),
            ],
        ]
    return InlineKeyboardMarkup(keyboard)


async def start_cf(update: Update, context: CallbackContext):
    match = re.match(r'/[\S]+\s+(.+)', update.message.text)
    if match is None:
        if update.message.reply_to_message is not None:
            user_id = update.message.reply_to_message.from_user.id
        else:
            username_1 = get_username_by_id(update.message.from_user.id)
            new_game_state = {"message_id": "", "player_ids": [update.message.from_user.id, None], "player_usernames": [username_1, ""], "current_turn": random.choice([0, 1]), "board": [[-1 for col in range(0, 7)] for row in range(0, 6)], "winner": None,}
            message = await update.message.reply_text(f"{format_playing_field(new_game_state)}", reply_markup=get_cf_keyboard(True), do_quote=False)
            new_game_state["message_id"] = str(message.chat_id) + "/" + str(message.message_id)
            games_data.append(new_game_state)
            clean_old_games()
            return
    else:
        user_id = parse_userid(match.group(1), context)

    if user_id is None:
        await update.message.reply_text(
            f"Кто такой \"{match.group(1)}\"? Что-то я таких не знаю...", do_quote=False)
        return
    elif str(user_id) == str(update.message.from_user.id):
        await update.message.reply_text("Одиноко? Можешь поиграть со мной! Правда я не очень хорошо умею играть в это (⁄ ⁄•⁄ω⁄•⁄ ⁄)", do_quote=True)
        return
    
    username_1 = get_username_by_id(update.message.from_user.id)
    # Hack... should be included in the get username function maybe?
    username_2 = context.bot.username if int(user_id) == context.bot.id else get_username_by_id(user_id)
    first_turn = 0 if int(user_id) == context.bot.id else random.choice([0, 1]) 
    new_game_state = {"message_id": "", "player_ids": [update.message.from_user.id, int(user_id)], "player_usernames": [username_1, username_2], "current_turn": first_turn, "board": [[-1 for col in range(0, 7)] for row in range(0, 6)], "winner": None,}
    message = await update.message.reply_text(f"{format_playing_field(new_game_state)}", reply_markup=get_cf_keyboard(False), do_quote=False)
    new_game_state["message_id"] = str(message.chat_id) + "/" + str(message.message_id)
    games_data.append(new_game_state)
    clean_old_games()


def get_cell_emoji(cell_value: int) -> str:
    if cell_value == -1:
        return "▪️"
    if cell_value == 0:
        return "🔴"
    if cell_value == 1:
        return "🔵"
    return "??"


def check_win_condition_on_cell(game_state, row_i: int, col_i: int) -> bool:
    dirs = [(1, 0), (0, 1), (1, 1), (1, -1)]
    player_i = game_state['board'][row_i][col_i]
    MAX_SCORE = 4
    for dir in dirs:
        score = 1
        for sign in [1, -1]:
            for i in range(1, MAX_SCORE):
                curr_row  = row_i + dir[1] * i * sign
                curr_col = col_i + dir[0] * i * sign
                if  curr_row < 0 or curr_col < 0 or curr_row >= len(game_state['board']) or curr_col >= len(game_state['board'][row_i]):
                    break
                if game_state['board'][curr_row][curr_col] == player_i:
                    score += 1
                else:
                    break
        if score >= MAX_SCORE:
            return True
    return False


def check_draw(game_state) -> bool:
    for col in game_state['board'][0]:
        if col == -1:
            return False
    return True


async def on_cf_action(update: Update, context: CallbackContext):
    query = update.callback_query
    # Not checking for whitelist because its broken with callback query...
    # But we still check if the message from query exists in our database so all is good!
    game_state = None
    message_id = str(query.message.chat_id) + "/" + str(query.message.message_id)
    for state in games_data:
        if state["message_id"] == message_id:
            game_state = state
            break
            
    if game_state is None:
        await query.answer("Не могу найти данные этой игры :(")
        return
    
    if query.data == "cf_join":
        if game_state['player_ids'][1] is None and query.from_user.id != game_state['player_ids'][0]:
            game_state['player_ids'][1] = query.from_user.id
            game_state['player_usernames'][1] = get_username_by_id(query.from_user.id)
            try:
                await query.edit_message_text(text=format_playing_field(game_state), reply_markup=get_cf_keyboard(False))
            except:
                game_state['player_ids'][1] = None
        await query.answer()
        return

    player_index = -1
    for i in range(0, 2):
        if query.from_user.id  == game_state["player_ids"][i]:
            player_index = i
            break

    if player_index != game_state["current_turn"] or game_state["winner"] is not None:
        await query.answer()
        return
    
    prev_game_state = json.loads(json.dumps(game_state))

    col_index = int(query.data[3:]) - 1
    row_index = -1
    for row_i in range(len(game_state['board']) - 1, -1, -1):
        if game_state['board'][row_i][col_index] == -1:
            row_index = row_i
            game_state['board'][row_i][col_index] = player_index
            break
    if row_index == -1:
        await query.answer(f'Столбец {col_index + 1} уже заполнен!')
        return

    if check_win_condition_on_cell(game_state, row_index, col_index):
        game_state["winner"] = player_index
    elif check_draw(game_state):
        game_state["winner"] = -1
    else:
        game_state["current_turn"] = (game_state["current_turn"] + 1) % 2
        if game_state["player_ids"][1] == context.bot.id:
            cols_to_check = [col_index]
            if col_index + 1 < len(game_state['board'][0]):
                cols_to_check.append(col_index + 1)
            if col_index - 1 >= 0:
                cols_to_check.append(col_index - 1)
            random.shuffle(cols_to_check)
            if col_index + 2 < len(game_state['board'][0]):
                cols_to_check.append(col_index + 2)
            if col_index - 2 >= 0:
                cols_to_check.append(col_index - 2)
            
            bot_row_index = -1
            bot_col = -1
            for col in cols_to_check:
                for row_i in range(len(game_state['board']) - 1, -1, -1):
                    if game_state['board'][row_i][col] == -1:
                        bot_row_index = row_i
                        bot_col = col
                        game_state['board'][row_i][col] = 1
                        break
                if bot_row_index != -1:
                    break
            
            if bot_row_index != -1:
                if check_win_condition_on_cell(game_state, bot_row_index, bot_col):
                    game_state["winner"] = 1
                elif check_draw(game_state):
                    game_state["winner"] = -1
            game_state["current_turn"] = (game_state["current_turn"] + 1) % 2

    if game_state["winner"] is not None:
        edit_res = await try_edit(query, game_state, None)
        if edit_res:
            games_data.remove(game_state)
        else:
            for index, state in enumerate(games_data):
                if state == game_state:
                    games_data[index] = prev_game_state
    else:
        edit_res = await try_edit(query, game_state, query.message.reply_markup)
        if not edit_res:
            for index, state in enumerate(games_data):
                if state == game_state:
                    games_data[index] = prev_game_state


async def try_edit(query, game_state, reply_markup = None) -> bool:
    try:
        await query.edit_message_text(text=format_playing_field(game_state), reply_markup=reply_markup)
        await query.answer()
        return True
    # On RetryAfter its guaranteed that the message wont be updated. However if we encounter some other weird error then the message is PROBABLY updated so we return true
    except RetryAfter:
        await query.answer("Не получилось обновить игру из-за защиты от спама :(")
        return False
    except Exception as e:
        #print(traceback.format_exc())
        print(e)
        await query.answer()
        return True


def subscribe(a: Application):
    a.add_handler(CommandHandler(("connectfour", "cf"), start_cf))
    a.add_handler(CallbackQueryHandler(on_cf_action, pattern="^cf_"))
