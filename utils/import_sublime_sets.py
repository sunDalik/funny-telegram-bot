import sys
import os
import json
import redis
import re

# TODO Move all redis data (schema, port, db index) into a separate file?
DICTIONARY_HASH = 'dictionary'

if __name__ == '__main__':
    JSON_PATH = os.path.join(os.path.dirname(__file__), "../_secrets/messages.json") 

    r = redis.Redis(host='localhost', port=6379, db=1)

    with open(JSON_PATH, 'r') as f:
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
            val = match.group(2)
            r.hset(DICTIONARY_HASH, key, val)
            sets_found += 1
            #print(f"Set {key} = {val}")
    print(f"Successfuly imported {sets_found} sets")