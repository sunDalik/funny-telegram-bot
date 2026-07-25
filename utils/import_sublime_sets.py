import sys
import os
import json
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from db import Database, GetVal
import getval

DB_PATH = os.path.join(os.path.dirname(__file__), '../bot.db')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Provide chat history JSON as an argument")
        sys.exit(1)

    json_path = sys.argv[1]
    inp = input("Are you sure? This is a potentially dangerous operation that can overwrite your database entries. Type \"Yes\" to continue\n")
    if (inp != "Yes"):
        print("Operation aborted")
        sys.exit(1)

    db = Database(DB_PATH)

    with open(json_path, 'r') as f:
        data = json.load(f)
        sets_found = 0
        for message in data['messages']:
            if ("text_entities" not in message):
                continue
            text = "".join([txt.get("text") for txt in message.get("text_entities")]).strip()
            if (text == ""):
                continue
            match = re.match(r'/set\s+([\S]+)\s+(.+)', text, re.DOTALL)
            if match is None:
                continue
            key = match.group(1)
            type, val_data, val_caption = getval.parse_set_data(match.group(2))
            db.insert(GetVal(key=key, type=type, data=val_data, caption=val_caption))
            sets_found += 1
            #print(f"Set {key} = {val_data}")
    db.commit()
    print(f"Successfuly imported {sets_found} sets")
