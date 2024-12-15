from typing import Deque, Dict, List, Tuple
from collections import deque
from dataclasses import dataclass
from telegram import CallbackQuery, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import RetryAfter
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from utils import in_whitelist
from _secrets import taki_suspects
import redis_db
import re
import random
import copy

MAX_ATTEMPTS = 5

DEFAULT_DIFFICULTY = 3
DIFFICULTIES: Dict[int, str] = {
    1: "Легенда",
    2: "Бинаурал",
    3: "Классика",
    4: "Тетрафоб",
    5: "Пентакулум",
    6: "Револьвер",
    7: "Патинко"
}

# The second message is hidden after the game is finished
START_MESSAGES: List[Tuple[str, str]] = [
    ("Дружок-пирожок оставил вам необычное послание:", "Узнали?"),
    ("Последний раз подозреваемого видели в соседней закусочной, где он произнес:", "Найдите мне этого пса!"),
    ("Как любил говорить один мудрец:", "Кто бы это мог быть?"),
]
LOSE_MESSAGES = [
    "Задание провалено, жалкие псы!",
    "Удачи в другой раз, ослы!",
    "Ваша игра подошла к концу, кабанчики.",
]

RKEY_BEST_STREAK = "takistreaks"
RKEY_CURR_STREAK = "takicurrstreak"
RKEY_SCORE = "takiscore"
RKEY_TOTAL_TRIES = "takitotaltries"
RKEY_TOTAL_WINS = "takitotalwins"


@dataclass
class GameState:
    game_message_id: str
    difficulty: int
    suspect_uid: int
    suspect_name: str
    suspect_msgs: List[str]
    guesses: List[int]
    guesser_uids: List[int]
    start_msgs: Tuple[str, str]
    action_log: str

    def is_lost(self):
        return len(self.guesses) >= MAX_ATTEMPTS

    def is_won(self):
        return self.suspect_uid in self.guesses and len(self.guesses) < MAX_ATTEMPTS

    def is_finished(self):
        return self.is_won() or self.is_lost()


games_data: Deque[GameState] = deque([], maxlen=10)

# Length of the previous suspect queue determines the penalty during the raffle to reduce twice-in-a-row picks
prev_suspect_uids: Deque[int] = deque([], maxlen=4)

r = redis_db.connect()


def format_playing_field(game: GameState) -> str:
    text = "Таки сложности " + DIFFICULTIES[game.difficulty] + ". "
    text += game.start_msgs[0]
    text += "\n\n"
    for msg in game.suspect_msgs:
        text += "* " + msg + "\n"
    if not game.is_finished():
        text += "\n"
        text += game.start_msgs[1]
    text += "\n"
    if game.action_log != "":
        text += "\n"
        text += game.action_log
        text += "\n"
    text += "\n"

    attempts_left = MAX_ATTEMPTS
    for g in game.guesses:
        attempts_left -= 1
        text += "🏆" if g == game.suspect_uid else "💀"
    for _ in range(0, attempts_left):
        text += "🏆" if game.is_won() else "🤔"

    return text


def get_taki_keyboard(guesses: List[int]) -> InlineKeyboardMarkup:
    keys = [
        InlineKeyboardButton(text=f"❌ {name}" if uid in guesses else name, callback_data=f"t_{uid}")
        for uid, (name, _) in taki_suspects.items()
    ]
    num_cols = 3
    key_rows = [keys[i:i+num_cols] for i in range(0, len(keys), num_cols)]
    return InlineKeyboardMarkup(key_rows)


def takistart(update: Update, context: CallbackContext):
    if not in_whitelist(update):
        return

    # Do not allow starting a new game until the current one is finished (can be abused for stats)
    if len(games_data) > 0 and not games_data[-1].is_finished():
        update.message.reply_text("Эй, сначала закончи прошлую игру!", reply_to_message_id=games_data[-1].game_message_id.split('/')[1])
        return

    difficulty = DEFAULT_DIFFICULTY
    diff_match = re.match(r'/[\S]+\s+(\d+)', update.message.text)
    if diff_match is not None:
        if (req_diff := int(diff_match.group(1))) in DIFFICULTIES:
            difficulty = req_diff
        else:
            update.message.reply_text("Это уже слишком, приятель. Выбери сложность из: " + ", ".join(map(str, DIFFICULTIES.keys())), quote=True)
            return

    prev_suspects = list(prev_suspect_uids)
    def penalize_prev(uid, ts): return ts // (1 + prev_suspects.index(uid)) if uid in prev_suspects else ts
    raffle = sum([
        [(sus_uid, sus_name)] * penalize_prev(sus_uid, sus_tickets)
        for sus_uid, (sus_name, sus_tickets) in taki_suspects.items()
    ], [])

    sus_uid, sus_name = random.choice(raffle)
    try:
        all_sus_msgs = [
            m.text
            for m in redis_db.messages
            # Ignore long messages, messages with just one word, and links (to avoid Telegram inserting link previews in the game message)
            if m.uid == sus_uid and len(m.text) < 300 and m.text.count(' ') >= 2 and not "https://" in m.text
        ]
        sus_msgs = random.sample(all_sus_msgs, difficulty)
    except Exception as e:
        print(e)
        return

    new_game = GameState(game_message_id="", difficulty=difficulty, suspect_uid=sus_uid, suspect_name=sus_name,
                         suspect_msgs=sus_msgs, guesses=[], guesser_uids=[], start_msgs=random.choice(START_MESSAGES), action_log="")
    message = update.message.reply_text(format_playing_field(new_game), reply_markup=get_taki_keyboard([]), quote=False)
    new_game.game_message_id = str(message.chat_id) + "/" + str(message.message_id)
    games_data.append(new_game)
    prev_suspect_uids.append(sus_uid)


def takistats(update: Update, context: CallbackContext):
    difficulty = DEFAULT_DIFFICULTY
    diff_match = re.match(r'/[\S]+\s+(\d+)', update.message.text)
    if diff_match is not None:
        if (req_diff := int(diff_match.group(1))) in DIFFICULTIES:
            difficulty = req_diff
        else:
            update.message.reply_text("Это уже слишком, приятель. Выбери сложность из: " + ", ".join(map(str, DIFFICULTIES.keys())), quote=True)
            return

    user_cache = {}

    text = "Мастера Таки сложности " + DIFFICULTIES[difficulty] + "\n"
    text += "\nСамые именитые:\n"
    scores = r.zrevrangebyscore(f"{RKEY_SCORE}_{difficulty}", min=0, max=2**31-1, withscores=True)
    for i, (uid, score) in enumerate(scores):
        if uid not in user_cache:
            user_cache[uid] = redis_db.get_username_by_id(uid)
        text += f"{i + 1}) {user_cache[uid]} — {int(score)}\n"
    if len(scores) == 0:
        text += "-\n"

    text += "\nСамые удачливые:\n"
    streaks = r.zrevrangebyscore(f"{RKEY_BEST_STREAK}_{difficulty}", min=0, max=2**31-1, withscores=True)
    for i, (uid, streak) in enumerate(streaks):
        if uid not in user_cache:
            user_cache[uid] = redis_db.get_username_by_id(uid)
        text += f"{i + 1}) {user_cache[uid]} — {int(streak)}\n"
    if len(streaks) == 0:
        text += "-\n"

    text += "\nСамые меткие:\n"
    tries = r.zrevrangebyscore(f"{RKEY_TOTAL_TRIES}_{difficulty}", min=1, max=2**31-1, withscores=True)
    wins = r.zrevrangebyscore(f"{RKEY_TOTAL_WINS}_{difficulty}", min=0, max=2**31-1, withscores=True)
    kdratios = [(uid_t, (float(num_wins) / float(num_tries)) * 100.0)
                for uid_t, num_tries in tries for uid_w, num_wins in wins if uid_t == uid_w]
    kdratios.sort(key=lambda t: t[1], reverse=True)
    for i, (uid, ratio) in enumerate(kdratios):
        if uid not in user_cache:
            user_cache[uid] = redis_db.get_username_by_id(uid)
        text += f"{i + 1}) {user_cache[uid]} — {int(ratio)}%\n"
    if len(kdratios) == 0:
        text += "-\n"

    update.message.reply_text(text, quote=False)


def on_taki_action(update: Update, context: CallbackContext):
    query = update.callback_query
    message_id = str(query.message.chat_id) + "/" + str(query.message.message_id)
    game = next((game for game in games_data if game.game_message_id == message_id), None)
    if game is None:
        query.answer("Не могу найти данные этой игры :(")
        return

    guess_uid = int(query.data[2:])
    guess_name = next((name for uid, (name, _) in taki_suspects.items() if uid == guess_uid), "???")
    if guess_uid in game.guesses:
        query.answer()
        return

    prev_game = copy.deepcopy(game)
    game.guesses.append(guess_uid)
    game.guesser_uids.append(query.from_user.id)
    has_won = game.suspect_uid == guess_uid and len(game.guesses) <= MAX_ATTEMPTS
    has_won_on_first_try = len([1 for g_id in game.guesser_uids if g_id == query.from_user.id]) == 1
    score_if_won = 1 + MAX_ATTEMPTS - len(game.guesses)

    guesser_name = redis_db.get_username_by_id(query.from_user.id)

    commit_game = False
    if has_won or len(game.guesses) >= MAX_ATTEMPTS:
        if has_won:
            game.action_log = f"{guesser_name} угадывает подозреваемого {guess_name}"
            streak = 0
            is_best_streak = False
            if has_won_on_first_try:
                streak = 1 + int(r.zscore(f"{RKEY_CURR_STREAK}_{game.difficulty}", query.from_user.id) or 0)
                is_best_streak = streak > (r.zscore(f"{RKEY_BEST_STREAK}_{game.difficulty}", query.from_user.id) or 0)
            if streak > 1:
                if is_best_streak:
                    game.action_log += f", получает +{score_if_won} и несется вперед с новым лучшим стриком из {streak}!"
                else:
                    game.action_log += f", получает +{score_if_won} и несется вперед со стриком из {streak}."
            else:
                game.action_log += f" и получает +{score_if_won}."
            game.action_log += " Good job!"
        else:
            game.action_log = f"Подозреваемый {game.suspect_name} скрывается в закате. {random.choice(LOSE_MESSAGES)}"

        if commit_game := try_edit(query, game, None):
            games_data.remove(game)
        else:
            for index, stored_game in enumerate(games_data):
                if stored_game == game:
                    games_data[index] = prev_game
    else:
        game.action_log = f"{guesser_name} выбирает подозреваемого {guess_name}..."
        if not (commit_game := try_edit(query, game, get_taki_keyboard(game.guesses))):
            for index, stored_game in enumerate(games_data):
                if stored_game == game:
                    games_data[index] = prev_game

    if commit_game:
        r.zincrby(f"{RKEY_TOTAL_TRIES}_{game.difficulty}", 1, query.from_user.id)
        if has_won:
            r.zincrby(f"{RKEY_TOTAL_WINS}_{game.difficulty}", 1, query.from_user.id)
            r.zincrby(f"{RKEY_SCORE}_{game.difficulty}", score_if_won, query.from_user.id)
            for guesser_id in set(game.guesser_uids):
                if guesser_id != query.from_user.id:
                    r.zrem(f"{RKEY_CURR_STREAK}_{game.difficulty}", guesser_id)
            if has_won_on_first_try:
                streak = r.zincrby(f"{RKEY_CURR_STREAK}_{game.difficulty}", 1, query.from_user.id)
                if streak > (r.zscore(f"{RKEY_BEST_STREAK}_{game.difficulty}", query.from_user.id) or 0):
                    r.zadd(f"{RKEY_BEST_STREAK}_{game.difficulty}", {query.from_user.id: streak})
            else:
                r.zrem(f"{RKEY_CURR_STREAK}_{game.difficulty}", query.from_user.id)
        elif len(game.guesses) >= MAX_ATTEMPTS:
            # Your streaks end here, partners. Easy come, easy go...
            for guesser_id in set(game.guesser_uids):
                r.zrem(f"{RKEY_CURR_STREAK}_{game.difficulty}", guesser_id)


def try_edit(query: CallbackQuery, game: GameState, reply_markup) -> bool:
    try:
        query.edit_message_text(text=format_playing_field(game), reply_markup=reply_markup)
        query.answer()
        return True
    except RetryAfter:
        query.answer("Не получилось обновить игру из-за защиты от спама :(")
        return False
    except Exception as e:
        print(e)
        query.answer()
        return True


def subscribe(u: Updater):
    u.dispatcher.add_handler(CommandHandler(("taki"), takistart))
    u.dispatcher.add_handler(CommandHandler(("takistats"), takistats))
    u.dispatcher.add_handler(CallbackQueryHandler(on_taki_action, pattern="^t_"))
