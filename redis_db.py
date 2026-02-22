import redis


_connection = None


def connect():
    global _connection
    if _connection is None:
        _connection = redis.Redis(host='localhost', port=6379, db=1, decode_responses=True)
    return _connection
