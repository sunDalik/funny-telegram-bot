import redis

_connection = None


def connect():
    global _connection
    if _connection is None:
        _connection = redis.Redis(host='localhost', port=6379, db=1)
    return _connection


USER_ID_TO_NAME = 'users'


def get_username_by_id(id) -> str:
    if id is None:
        return "???"
    username = connect().hget(USER_ID_TO_NAME, id)
    username = username.decode('utf-8') if username else str(id)
    return username


def update_user_data(id, username):
    if username is None:
        return
    connect().hset(USER_ID_TO_NAME, id, username)


def reverse_lookup_id(username):
    username = username[1:] if username.startswith("@") else username
    for key, value in connect().hgetall(USER_ID_TO_NAME).items():
        if (value.decode("utf-8").lower() == username.lower()):
            return key.decode("utf-8")
