from dataclasses import dataclass
from typing import List
import redis
import json
from _secrets import banned_user_ids
import telegram


@dataclass
class TextMessage:
    uid: int
    ts: int
    text: str

    def encode(self) -> str:
        return json.dumps({'uid': self.uid, 'ts': self.ts, 'text': self.text})

    def decode(d: str):
        dd = json.loads(d)
        return TextMessage(uid=dd['uid'], ts=dd['ts'], text=dd['text'])


messages: List[TextMessage] = []

_connection = None
_RECIEVED_MESSAGES = "received_tg_messages"
_USER_ID_TO_NAME = 'users'


def connect():
    global _connection
    if _connection is None:
        _connection = redis.Redis(host='localhost', port=6379, db=1, decode_responses=True)
    return _connection


def load_messages():
    global messages
    messages = []
    f = open('_secrets/messages.json')
    data = json.load(f)
    banned_user_ids_str = [str(id) for id in banned_user_ids]
    for message in data['messages']:
        # Ignore reposts
        if not "from_id" in message or not message['from_id'].startswith('user'):
            continue
        uid_str = message['from_id'][4:]
        # Ingore messages from banned users
        if uid_str in banned_user_ids_str:
            continue
        # Ignore forwarded messages
        forwarded_from = message.get("forwarded_from", None)
        if forwarded_from is not None and forwarded_from != "null":
            continue
        if "text_entities" in message:
            text = "".join([txt.get("text") for txt in message.get("text_entities")])
            if text != "" and not text.startswith("/"):
                ts = int(message["date_unixtime"]) if "date_unixtime" in message else 0
                messages.append(TextMessage(uid=int(uid_str), ts=ts, text=text))
    print(f'Loaded {len(messages)} messages from messages.json')
    f.close()

    rdb_loaded = 0
    for msg in connect().lrange(_RECIEVED_MESSAGES, 0, -1):
        rdb_loaded += 1
        messages.append(TextMessage.decode(msg))
    print(f'Loaded {rdb_loaded} messages from Redis')

    if len(messages) == 0:
        # The bot assumes that the messages list is never empty so if there is none we put a default message there
        messages.append(TextMessage(uid=0, ts=0, text="Привет!"))


def record_message(message: telegram.Message):
    text_message = TextMessage(uid=message.from_user.id, ts=int(message.date.timestamp()), text=message.text)
    messages.append(text_message)
    connect().rpush(_RECIEVED_MESSAGES, text_message.encode())
    update_user_data(message.from_user)


def get_username_by_id(id) -> str:
    if id is None:
        return "???"
    username = connect().hget(_USER_ID_TO_NAME, str(id))
    username = username if username else str(id)
    return username


def update_user_data(user: telegram.User):
    username = user.username
    if username is None:
        username = user.first_name
        if username is None:
            return

    connect().hset(_USER_ID_TO_NAME, str(user.id), username)


def reverse_lookup_id(username):
    username = username[1:] if username.startswith("@") else username
    for key, value in connect().hgetall(_USER_ID_TO_NAME).items():
        if (value.lower() == username.lower()):
            return int(key)
    return None
