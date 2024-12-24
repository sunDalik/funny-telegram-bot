import copy
from datetime import datetime, timedelta
import logging
import logging.handlers
import math
from typing import Dict, List
from _secrets import lucky_numbers
import markovify
from telegram import Update
from telegram.ext import Updater, CommandHandler
import re
import redis_db
from utils import in_whitelist
from difflib import SequenceMatcher

r = redis_db.connect()
logger = logging.getLogger(__name__)
again_setter = None
markov_chain = None
markov_chain_timestamp = None

NORMALIZE_CHAIN_INPUT = True
MAX_QUERY_BIAS_DISTANCE = 12
MAX_TEXT_GEN_TRIES = 20000
MAX_TEXTS_FOR_SCORING = 50
MAX_WORDS_PER_TEXT = 20


def _create_chain_from_messages() -> markovify.Text:
    chain_input = "\n".join(m.text for m in redis_db.messages)
    if NORMALIZE_CHAIN_INPUT:
        chain_input_orig_len = len(chain_input)
        chain_input = chain_input.lower()
        # Drop all URLs
        chain_input = re.sub(r'https?://[^\s]*', '', chain_input)
        # Drop hyphens used as punctuation in place of dashes, but keep them in compound words
        chain_input = re.sub(r'\B-\B', ' ', chain_input)
        # Drop repeated punctuation
        chain_input = re.sub(r'([?])[?]+|([!])[!]+', r'\g<1>\g<2>', chain_input)
        # Drop username markers and inessential punctuation to reduce the number of unique tokens
        normalize_chars = str.maketrans(';:—–⁃', '     ', '@"«»)(][}{_#%^&*')
        chain_input = chain_input.translate(normalize_chars)
        logger.info(f"[markov] Normalized chain input, trimming length from {chain_input_orig_len} to {len(chain_input)}")
    return markovify.Text(chain_input)


def _bias_transition_to_word(state: str, transitions: Dict[str, int], word: str, weight: float):
    if state == '___BEGIN__':
        # Avoid biasing the starting word too much, or all generated sentences will begin the same
        biased_freq = weight * 1.25 * (sum(transitions.values()) / len(transitions))
    else:
        biased_freq = weight * sum(transitions.values())
    transitions[word] = max(transitions[word], math.ceil(biased_freq))


def _create_biased_chain(orig_chain: markovify.Text, query: str) -> markovify.Text:
    biased_chain = copy.deepcopy(orig_chain)

    preds = {}
    num_transitions_biased = 0
    for state, transitions in biased_chain.chain.model.items():
        for word in transitions.keys():
            if word == query:
                _bias_transition_to_word(state[1], transitions, word, 1.0)
                preds[state[1]] = state[0]
                num_transitions_biased += 1
    if num_transitions_biased == 0:
        return None

    for d in range(MAX_QUERY_BIAS_DISTANCE):
        dist_decay = math.exp(-d / (0.8 * MAX_QUERY_BIAS_DISTANCE))
        pred_preds = {}
        for state, transitions in biased_chain.chain.model.items():
            for word in transitions.keys():
                if word in preds and preds[word] == state[1]:
                    _bias_transition_to_word(state[1], transitions, word, dist_decay)
                    pred_preds[state[1]] = state[0]
                    num_transitions_biased += 1
        preds = pred_preds

    logger.info(f"[markov] Biased {num_transitions_biased} transitions")
    biased_chain.chain.precompute_begin_state()
    return biased_chain


def _score_generated_text(t: str, prev_result_tokens: List[List[str]]) -> float:
    tt = t.split()
    # Penalize texts that are similar to the previously generated results
    max_prev_sim, avg_prev_sim = 0.0, 0.0
    if len(prev_result_tokens) > 0:
        prev_sims = [SequenceMatcher(None, tt, pt).ratio() for pt in prev_result_tokens]
        max_prev_sim = max(prev_sims)
        avg_prev_sim = sum(prev_sims) / len(prev_sims)
    prev_sim_score = (1.0 - max_prev_sim) + (1.0 - avg_prev_sim)
    # Penalize short texts (longer texts are generally more interesting)
    len_score = min(1.0, len(t) / 300)
    return prev_sim_score + len_score


def markovpost(update: Update, context, biased_chain=None, previous_results=[]):
    if not in_whitelist(update):
        return
    logger.info(f"[markov] {update.message.text}")

    global markov_chain
    global markov_chain_timestamp
    if markov_chain_timestamp is not None and datetime.now() > markov_chain_timestamp + timedelta(days=7):
        logger.info(f"[markov] Refreshing the model created on {markov_chain_timestamp}")
        markov_chain, markov_chain_timestamp = None, None
    if markov_chain is None:
        update.message.reply_text("Сначала я должен вспомнить всё... Подожди минутку", quote=True)
        markov_chain = _create_chain_from_messages()
        markov_chain_timestamp = datetime.now()
        logger.info(f"[markov] Initialized model with {len(markov_chain.chain.model)} states")

    match = re.match(r'/[\S]+\s+(.+)', update.message.text)
    if match is None:
        text = markov_chain.make_sentence(max_words=MAX_WORDS_PER_TEXT, tries=MAX_TEXT_GEN_TRIES)
        update.message.reply_text(text, quote=False)
    else:
        query = match.group(1).lower()
        if re.search(r'\s', query):
            update.message.reply_text(f"Я не умею шутить больше чем про одну вещь за раз >.< Выбери какое-нибудь одно слово", quote=True)
            return
        if biased_chain is None:
            if (biased_chain := _create_biased_chain(markov_chain, query)) is None:
                update.message.reply_text(f'Дружище, я рад, что тебя так забавляет "{query}", но я ничего смешного в этом не увидел...', quote=False)
                return

        texts = []
        for i in range(MAX_TEXT_GEN_TRIES):
            words = biased_chain.chain.walk()
            if len(words) <= MAX_WORDS_PER_TEXT and query in words:
                if biased_chain.test_sentence_output(words, max_overlap_ratio=0.7, max_overlap_total=10):
                    texts.append((" ".join(words), i))
                    if len(texts) >= MAX_TEXTS_FOR_SCORING:
                        break

        if len(texts) > 0:
            prev_result_tokens = [t.split() for t in previous_results]
            texts.sort(key=lambda t: _score_generated_text(t[0], prev_result_tokens), reverse=True)
            text, text_try = texts[0]
            if again_setter:
                again_setter(lambda: markovpost(update, context, biased_chain, previous_results + [text]))
            update.message.reply_text(f"Прикол #{text_try}{lucky_numbers.get(text_try, '')}. {text.capitalize()}", quote=False)
        else:
            update.message.reply_text(f'Что-то я ничего смешного про "{query}" не придумал...', quote=False)


def subscribe(u: Updater, _again_setter):
    u.dispatcher.add_handler(CommandHandler(("shitpost", "s"), markovpost))
    global again_setter
    again_setter = _again_setter
