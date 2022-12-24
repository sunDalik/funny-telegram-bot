import redis
import json
from _secrets import banned_user_ids
from telegram import User

_connection = None
messages = []

RECEIVED_MESSAGES_LIST = 'received_messages_list'
USER_ID_TO_NAME = 'users'


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
        if ("text_entities" in message):
            text = "".join([txt.get("text") for txt in message.get("text_entities")])
            # Ignore commands and messages from banned users
            # Skip "user" prefix from id... Telegram export does this for some reason
            if (text != "" and "from_id" in message and message['from_id'][4:] not in banned_user_ids_str and not text.startswith("/")):
                messages.append(text)
    f.close()

    for message in connect().lrange(RECEIVED_MESSAGES_LIST, 0, -1):
        messages.append(message)
    
    if (len(messages) == 0):
        # The bot assumes that the messages list is never empty so if there is none we put a default message there
        messages.append("Привет!")


def get_username_by_id(id) -> str:
    if id is None:
        return "???"
    username = connect().hget(USER_ID_TO_NAME, str(id))
    username = username if username else str(id)
    return username


def update_user_data(user: User):
    username = user.username
    if username is None:
        username = user.first_name
        if username is None:
            return

    connect().hset(USER_ID_TO_NAME, str(user.id), username)


def reverse_lookup_id(username):
    username = username[1:] if username.startswith("@") else username
    for key, value in connect().hgetall(USER_ID_TO_NAME).items():
        if (value.lower() == username.lower()):
            return int(key)
    return None
