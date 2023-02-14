from telegram import ParseMode, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import RetryAfter
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
import redis_db
import re
from utils import in_whitelist, parse_userid, PUNCTUATION_REGEX
import random
import json
import traceback

r = redis_db.connect()

games_data = []
MAX_INCORRECT_GUESSES = 8

def format_playing_field(game_state) -> str:
    if game_state['creation']:
        return f"{redis_db.get_username_by_id(game_state['creator_id'])} загадывает слово..."
    text = ""
    if game_state['incorrect_guesses'] >= MAX_INCORRECT_GUESSES:
        text = f"Чел умер... Довольны?\n(Ответ: \"{game_state['answer'].upper()}\")\n\n"
    elif is_game_won(game_state):
        text = "Победа!\n\n"
    
    text += f"{game_state['last_action']}\n" 

    for i in range(0, game_state['incorrect_guesses']):
        text += "💀"
    for i in range(game_state['incorrect_guesses'], MAX_INCORRECT_GUESSES):
        text += "😊"

    text += "\n\n"

    for c in game_state['answer']:
        if c == " ":
            text += "   "
        elif c.lower() in game_state['guesses']:
            text += c.upper() + " "
        else:
            text += "_ "
    
    text += "\n\n"

    for c in game_state['guesses']:
            text += c.lower() + " "
    return text


def clean_old_games():
    global games_data
    MAX_GAMES = 10
    remove_games = max(0, len(games_data) - MAX_GAMES)
    games_data = games_data[remove_games:]


def get_hangman_keyboard(guesses, creation_phase: bool, lang: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("А", callback_data="h_а"),
            InlineKeyboardButton("Б", callback_data="h_б"),
            InlineKeyboardButton("В", callback_data="h_в"),
            InlineKeyboardButton("Г", callback_data="h_г"),
            InlineKeyboardButton("Д", callback_data="h_д"),
            InlineKeyboardButton("Е", callback_data="h_е"),
            InlineKeyboardButton("Ж", callback_data="h_ж"),
            InlineKeyboardButton("З", callback_data="h_з"),
        ],
        [
            InlineKeyboardButton("И", callback_data="h_и"),
            InlineKeyboardButton("Й", callback_data="h_й"),
            InlineKeyboardButton("К", callback_data="h_к"),
            InlineKeyboardButton("Л", callback_data="h_л"),
            InlineKeyboardButton("М", callback_data="h_м"),
            InlineKeyboardButton("Н", callback_data="h_н"),
            InlineKeyboardButton("О", callback_data="h_о"),
            InlineKeyboardButton("П", callback_data="h_п"),
        ],
        [
            InlineKeyboardButton("Р", callback_data="h_р"),
            InlineKeyboardButton("С", callback_data="h_с"),
            InlineKeyboardButton("Т", callback_data="h_т"),
            InlineKeyboardButton("У", callback_data="h_у"),
            InlineKeyboardButton("Ф", callback_data="h_ф"),
            InlineKeyboardButton("Х", callback_data="h_х"),
            InlineKeyboardButton("Ц", callback_data="h_ц"),
            InlineKeyboardButton("Ч", callback_data="h_ч"),
        ],
        [
            InlineKeyboardButton("Ш", callback_data="h_ш"),
            InlineKeyboardButton("Щ", callback_data="h_щ"),
            InlineKeyboardButton("Ъ", callback_data="h_ъ"),
            InlineKeyboardButton("Ы", callback_data="h_ы"),
            InlineKeyboardButton("Ь", callback_data="h_ь"),
            InlineKeyboardButton("Э", callback_data="h_э"),
            InlineKeyboardButton("Ю", callback_data="h_ю"),
            InlineKeyboardButton("Я", callback_data="h_я"),
        ],
    ] if lang == "ru" else [
        [
            InlineKeyboardButton("A", callback_data="h_a"),
            InlineKeyboardButton("B", callback_data="h_b"),
            InlineKeyboardButton("C", callback_data="h_c"),
            InlineKeyboardButton("D", callback_data="h_d"),
            InlineKeyboardButton("E", callback_data="h_e"),
            InlineKeyboardButton("F", callback_data="h_f"),
            InlineKeyboardButton("G", callback_data="h_g"),
        ],
        [
            InlineKeyboardButton("H", callback_data="h_h"),
            InlineKeyboardButton("I", callback_data="h_i"),
            InlineKeyboardButton("J", callback_data="h_j"),
            InlineKeyboardButton("K", callback_data="h_k"),
            InlineKeyboardButton("L", callback_data="h_l"),
            InlineKeyboardButton("M", callback_data="h_m"),
            InlineKeyboardButton("N", callback_data="h_n"),
        ],
        [
            InlineKeyboardButton("O", callback_data="h_o"),
            InlineKeyboardButton("P", callback_data="h_p"),
            InlineKeyboardButton("Q", callback_data="h_q"),
            InlineKeyboardButton("R", callback_data="h_r"),
            InlineKeyboardButton("S", callback_data="h_s"),
            InlineKeyboardButton("T", callback_data="h_t"),
            InlineKeyboardButton("U", callback_data="h_u"),
        ],
        [
            InlineKeyboardButton("V", callback_data="h_v"),
            InlineKeyboardButton("W", callback_data="h_w"),
            InlineKeyboardButton("X", callback_data="h_x"),
            InlineKeyboardButton("Y", callback_data="h_y"),
            InlineKeyboardButton("Z", callback_data="h_z"),
        ],
    ]
    for index, row in enumerate(keyboard):
        keyboard[index] = [button if button.text.lower() not in guesses else InlineKeyboardButton(" ", callback_data="h_blank") for button in row]

    if creation_phase:
        keyboard.append([InlineKeyboardButton("Пробел" if lang == "ru" else "Space", callback_data="h_ ")])
        keyboard.append([InlineKeyboardButton("DEL", callback_data="h_del"), InlineKeyboardButton("🆗", callback_data="h_ok")],)

    return InlineKeyboardMarkup(keyboard)


def start_hangman(update: Update, context: CallbackContext, lang: str):
    if (not in_whitelist(update)):
        return
    new_game_state = {"message_id": "", "answer": "", "guesses": [], "incorrect_guesses": 0, "last_action": "Игра началась!\n", "last_user_id": None, "creator_id": update.message.from_user.id, "creation": True, "l": lang}
    message = update.message.reply_text(f"{format_playing_field(new_game_state)}", reply_markup=get_hangman_keyboard([], True, lang), quote=False)
    new_game_state["message_id"] = str(message.chat_id) + "/" + str(message.message_id)
    games_data.append(new_game_state)
    clean_old_games()


def is_game_won(game_state) -> bool:
    if game_state['creation']:
        return False
    for c in game_state['answer']:
        if c != " " and c.lower() not in game_state['guesses']:
            return False
    return True


def on_hangman_action(update: Update, context: CallbackContext):
    query = update.callback_query
    # Not checking for whitelist because its broken with callback query...
    # But we still check if the message from query exists in our database so all is good!

    if query.data == 'h_blank':
        query.answer()
        return

    game_state = None
    message_id = str(query.message.chat_id) + "/" + str(query.message.message_id)
    for state in games_data:
        if state["message_id"] == message_id:
            game_state = state
            break
            
    if game_state is None:
        query.answer("Не могу найти данные этой игры :(")
        return
    
    if game_state['creation']:
        if query.from_user.id != game_state['creator_id']:
            query.answer()
            return

        if query.data == 'h_ok':
            if len(game_state['answer'].strip()) <= 2:
                query.answer("Слишком короткое слово!")
                return
            game_state['creation'] = False
            edit_res = try_edit(query, game_state, get_hangman_keyboard(game_state['guesses'], False, game_state['l']))
            if not edit_res:
                game_state['creation'] = True
            query.answer()
            return
        elif query.data == 'h_del':
            if len(game_state['answer']) > 0:
                game_state['answer'] = game_state['answer'][:-1]
            query.answer(f"Ввод: {game_state['answer']}")
            return
        else:
            letter = query.data[2:].lower()
            game_state['answer'] += letter
            query.answer(f"Ввод: {game_state['answer']}")
            return
    
    if query.data == 'h_ok' or query.data == 'h_del':
        query.answer()
        return

    if game_state["incorrect_guesses"] >= MAX_INCORRECT_GUESSES or is_game_won(game_state):
        query.answer()
        return
    
    if query.from_user.id == game_state['creator_id']:
        query.answer("Ты не можешь угадывать в своей игре!")
        return
    
    if query.from_user.id == game_state['last_user_id']:
        query.answer("Ты не можешь угадывать сразу после неудачной попытки!")
        return

    letter = query.data[2:].lower()
    if letter in game_state['guesses']:
        query.answer()
        return

    prev_game_state = json.loads(json.dumps(game_state))
    game_state['guesses'].append(letter)
    game_state['last_action'] = f"{redis_db.get_username_by_id(query.from_user.id)} выбрал букву {letter.upper()}.  "

    if letter in game_state['answer']:
        game_state['last_action'] += "✅"
        game_state['last_user_id'] = None
    else:
        game_state['last_action'] += "❌"
        game_state['incorrect_guesses'] += 1
        game_state['last_user_id'] = query.from_user.id
    
    if game_state["incorrect_guesses"] >= MAX_INCORRECT_GUESSES or is_game_won(game_state):
        edit_res = try_edit(query, game_state, None)
        if edit_res:
            games_data.remove(game_state)
        else:
            for index, state in enumerate(games_data):
                if state == game_state:
                    games_data[index] = prev_game_state
    else:
        edit_res = try_edit(query, game_state, get_hangman_keyboard(game_state['guesses'], False, game_state['l']))
        if not edit_res:
            for index, state in enumerate(games_data):
                if state == game_state:
                    games_data[index] = prev_game_state


def try_edit(query, game_state, reply_markup = None) -> bool:
    try:
        query.edit_message_text(text=format_playing_field(game_state), reply_markup=reply_markup)
        query.answer()
        return True
    except RetryAfter:
        query.answer("Не получилось обновить игру из-за защиты от спама :(")
        return False
    except Exception as e:
        #print(traceback.format_exc())
        print(e)
        query.answer()
        return True


def subscribe(u: Updater):
    u.dispatcher.add_handler(CommandHandler(("hangman"), lambda update, context: start_hangman(update, context, "ru")))
    u.dispatcher.add_handler(CommandHandler(("hangman_english"), lambda update, context: start_hangman(update, context, "en")))
    u.dispatcher.add_handler(CallbackQueryHandler(on_hangman_action, pattern="^h_"))