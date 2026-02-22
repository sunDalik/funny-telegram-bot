import os
import sys
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from db import M, MR, U

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'bot.db')

if __name__ == '__main__':
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(f"""
        CREATE TABLE IF NOT EXISTS {M.TABLE} (
            {M.MSG_ID}  INTEGER PRIMARY KEY,
            {M.USER_ID} INTEGER NOT NULL,
            {M.TS}      INTEGER NOT NULL,
            {M.TEXT}    TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_{M.TABLE}_{M.USER_ID}
            ON {M.TABLE}({M.USER_ID});
        CREATE INDEX IF NOT EXISTS idx_{M.TABLE}_{M.TS}
            ON {M.TABLE}({M.TS});

        CREATE TABLE IF NOT EXISTS {MR.TABLE} (
            {MR.MSG_ID}  INTEGER NOT NULL,
            {MR.USER_ID} INTEGER NOT NULL,
            {MR.EMOJI}   TEXT NOT NULL,
            {MR.TS}      INTEGER NOT NULL,
            PRIMARY KEY ({MR.MSG_ID}, {MR.USER_ID}, {MR.EMOJI})
        );
        CREATE INDEX IF NOT EXISTS idx_{MR.TABLE}_{MR.EMOJI}_{MR.MSG_ID}
            ON {MR.TABLE}({MR.EMOJI}, {MR.MSG_ID});

        CREATE TABLE IF NOT EXISTS {U.TABLE} (
            {U.USER_ID}   INTEGER PRIMARY KEY,
            {U.USERNAME}  TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()
    print(f"Initialized {os.path.abspath(DB_PATH)}")
