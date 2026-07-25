import sys
import os
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from db import Database, GetVal
import getval
import redis_db

DB_PATH = os.path.join(os.path.dirname(__file__), '../bot.db')
DICTIONARY_HASH = 'dictionary'

if __name__ == '__main__':
    inp = input("Are you sure? This will overwrite existing gets. Type \"Yes\" to continue\n")
    if (inp != "Yes"):
        print("Operation aborted")
        sys.exit(1)

    r = redis_db.connect()
    rawvals = r.hgetall(DICTIONARY_HASH)

    db = Database(DB_PATH)
    types = Counter()
    for key, rawval in rawvals.items():
        type, data, caption = getval.parse_rawget(rawval)
        db.insert(GetVal(key=key, type=type, data=data, caption=caption))
        types[type] += 1
    db.commit()

    print(f"Imported {len(rawvals)} gets")
    for type, count in sorted(types.items()):
        print(f"  {type}: {count}")
