import sys
import os
import json
import redis
import re

# TODO Move all redis data (schema, port, db index) into a separate file?
DICTIONARY_HASH = 'dictionary'

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Provide chat history JSON as an argument")
        sys.exit(1)

    json_path = sys.argv[1]
    inp = input("Are you sure? This is a potentially dangerous operation that can overwrite your database entries. Type \"Yes\" to continue\n")
    if (inp != "Yes"):
        print("Operation aborted")
        sys.exit(1)

    r = redis.Redis(host='localhost', port=6379, db=1)

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
            val = match.group(2)
            r.hset(DICTIONARY_HASH, key, val)
            sets_found += 1
            #print(f"Set {key} = {val}")
    print(f"Successfuly imported {sets_found} sets")