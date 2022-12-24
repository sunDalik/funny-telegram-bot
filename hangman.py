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
    text = ""
    if game_state['incorrect_guesses'] >= MAX_INCORRECT_GUESSES:
        text = f"Чел умер... Довольны?\n(Ответ: \"{game_state['answer']}\")\n\n"
    elif is_game_won(game_state):
        text = "Победа!\n\n"
    
    text += f"{game_state['last_action']}\n" 

    for i in range(0, game_state['incorrect_guesses']):
        text += "💀"
    for i in range(game_state['incorrect_guesses'], MAX_INCORRECT_GUESSES):
        text += "😊"

    text += "\n\n"

    for c in game_state['answer']:
        if c.lower() in game_state['guesses']:
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


def get_hangman_keyboard(guesses) -> InlineKeyboardMarkup:
    keyboard_ru = [
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
    ]
    for index, row in enumerate(keyboard_ru):
        keyboard_ru[index] = [button for button in row if button.text.lower() not in guesses]
            
    return InlineKeyboardMarkup(keyboard_ru)


def start_hangman(update: Update, context: CallbackContext):
    if (not in_whitelist(update)):
        return

    shuffled_messages = redis_db.messages.copy()
    random.shuffle(shuffled_messages)
    result = ""
    word_regex = re.compile(r"^[А-Яа-яёЁ]{4,12}$")
    for rnd_message in shuffled_messages:
        words = [w for w in PUNCTUATION_REGEX.split(rnd_message) if w != ""]
        for word in words:
            if word_regex.match(word) is not None:
                word = word.replace("ё", "е")
                word = word.replace("Ё", "Е")
                result = word
                break

        if result != "":
            break

    if result == "":
        result = "Ошибка"

    new_game_state = {"message_id": "", "answer": result, "guesses": [], "incorrect_guesses": 0, "last_action": "Игра началась!\n", "last_user_id": -1}
    message = update.message.reply_text(f"{format_playing_field(new_game_state)}", reply_markup=get_hangman_keyboard([]), quote=False)
    new_game_state["message_id"] = str(message.chat_id) + "/" + str(message.message_id)
    games_data.append(new_game_state)
    clean_old_games()


def is_game_won(game_state) -> bool:
    for c in game_state['answer']:
        if c.lower() not in game_state['guesses']:
            return False
    return True


def on_hangman_action(update: Update, context: CallbackContext):
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
        query.answer("Не могу найти данные этой игры :(")
        return

    if game_state["incorrect_guesses"] >= MAX_INCORRECT_GUESSES or is_game_won(game_state):
        query.answer()
        return
    
    if query.from_user.id == game_state['last_user_id']:
        query.answer("Ты не можешь угадывать два хода подряд!")
        return

    letter = query.data[2:].lower()
    if letter in game_state['guesses']:
        query.answer()
        return

    prev_game_state = json.loads(json.dumps(game_state))
    game_state['guesses'].append(letter)
    game_state['last_action'] = f"{redis_db.get_username_by_id(query.from_user.id)} выбрал букву {letter.upper()}. "

    if letter in game_state['answer']:
        game_state['last_action'] += "Верно 😊"
    else:
        game_state['last_action'] += "Неверно 💀"
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
        edit_res = try_edit(query, game_state, get_hangman_keyboard(game_state['guesses']))
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
    u.dispatcher.add_handler(CommandHandler(("hangman"), start_hangman))
    u.dispatcher.add_handler(CallbackQueryHandler(on_hangman_action, pattern="^h_"))