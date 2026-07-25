import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass, fields, astuple
from typing import ClassVar, Type, TypeVar

T = TypeVar('T')


@dataclass
class Message:
    msg_id: int
    user_id: int
    ts: int
    text: str

    TABLE: ClassVar[str] = "messages"
    MSG_ID: ClassVar[str] = "msg_id"
    USER_ID: ClassVar[str] = "user_id"
    TS: ClassVar[str] = "ts"
    TEXT: ClassVar[str] = "text"


@dataclass
class MessageReaction:
    msg_id: int
    user_id: int
    emoji: str
    ts: int

    TABLE: ClassVar[str] = "message_reactions"
    MSG_ID: ClassVar[str] = "msg_id"
    USER_ID: ClassVar[str] = "user_id"
    EMOJI: ClassVar[str] = "emoji"
    TS: ClassVar[str] = "ts"


@dataclass
class User:
    user_id: int
    username: str

    TABLE: ClassVar[str] = "users"
    USER_ID: ClassVar[str] = "user_id"
    USERNAME: ClassVar[str] = "username"


@dataclass
class GetVal:
    key: str
    type: str
    data: str
    caption: str = ""

    TABLE: ClassVar[str] = "get_vals"
    KEY: ClassVar[str] = "key"
    TYPE: ClassVar[str] = "type"
    DATA: ClassVar[str] = "data"
    CAPTION: ClassVar[str] = "caption"


@dataclass
class GetJob:
    msg_id: int
    chat_id: int
    user_id: int
    get_key: str
    target_ts: int
    quote_text: str = ""
    quote_user: str = ""

    TABLE: ClassVar[str] = "get_jobs"
    MSG_ID: ClassVar[str] = "msg_id"
    CHAT_ID: ClassVar[str] = "chat_id"
    USER_ID: ClassVar[str] = "user_id"
    GET_KEY: ClassVar[str] = "get_key"
    TARGET_TS: ClassVar[str] = "target_ts"
    QUOTE_TEXT: ClassVar[str] = "quote_text"
    QUOTE_USER: ClassVar[str] = "quote_user"


@dataclass
class PyVar:
    key: str
    value: int

    TABLE: ClassVar[str] = "py_vars"
    KEY: ClassVar[str] = "key"
    VALUE: ClassVar[str] = "value"


M = Message
MR = MessageReaction
U = User
GV = GetVal
GJ = GetJob
PV = PyVar


class Database:
    def __init__(self, path: str):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")  # WAL for performance
        self._conn.execute("PRAGMA cache_size=-201327")  # Use 192 MiB RAM cache

    def fetch_many(self, cls: Type[T], sql: str, params: tuple = ()) -> list[T]:
        rows = self._conn.execute(sql, params).fetchall()
        return [cls(**dict(r)) for r in rows]

    def insert(self, item) -> None:
        cls = type(item)
        fs = [f.name for f in fields(cls)]
        sql = (f"INSERT OR REPLACE INTO {cls.TABLE}"
               f" ({', '.join(fs)}) VALUES ({', '.join('?' * len(fs))})")
        self._conn.execute(sql, astuple(item))

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self._conn.execute(sql, params)

    def commit(self) -> None:
        self._conn.commit()

    def record_message(self, msg_id: int, user_id: int, ts: int, text: str) -> None:
        self.insert(Message(msg_id=msg_id, user_id=user_id, ts=ts, text=text))
        self.commit()

    def record_reaction(self, msg_id: int, user_id: int, ts: int, added: set[str], removed: set[str]) -> None:
        for emoji in added:
            self.execute(
                f"INSERT OR REPLACE INTO {MR.TABLE} ({MR.MSG_ID}, {MR.USER_ID}, {MR.EMOJI}, {MR.TS}) VALUES (?,?,?,?)",
                (msg_id, user_id, emoji, ts))
        for emoji in removed:
            self.execute(
                f"DELETE FROM {MR.TABLE} WHERE {MR.MSG_ID}=? AND {MR.USER_ID}=? AND {MR.EMOJI}=?",
                (msg_id, user_id, emoji))
        if added or removed:
            self.commit()

    def load_py_vars(self) -> dict[str, int]:
        return dict(self.execute(f"SELECT {PV.KEY}, {PV.VALUE} FROM {PV.TABLE}"))

    def record_py_vars(self, values: Mapping[str, int | None], expected: Mapping[str, int] | None = None) -> dict[str, int | None]:
        previous_values = self.load_py_vars() if values and expected is None else {}
        if expected is None:
            self._conn.executemany(
                f"INSERT OR REPLACE INTO {PV.TABLE} ({PV.KEY}, {PV.VALUE}) VALUES (?,?)", values.items())
        else:
            # Avoid modifying vars that were updated after the expected snapshot is taken
            self._conn.executemany(
                f"UPDATE {PV.TABLE} SET {PV.VALUE}=? WHERE {PV.KEY}=? AND {PV.VALUE}=?",
                ((value, key, expected[key]) for key, value in values.items() if value is not None))
            self._conn.executemany(
                f"DELETE FROM {PV.TABLE} WHERE {PV.KEY}=? AND {PV.VALUE}=?",
                ((key, expected[key]) for key, value in values.items() if value is None))
        self.commit()
        return {key: previous_values.get(key) for key in values}


_db: Database | None = None


def init(path: str) -> Database:
    global _db
    _db = Database(path)
    # Check schema
    for table in (M.TABLE, MR.TABLE, U.TABLE, GV.TABLE, GJ.TABLE, PV.TABLE):
        _db.execute(f"SELECT 1 FROM {table} LIMIT 1")
    return _db


def get() -> Database:
    return _db
