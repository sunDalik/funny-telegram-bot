import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from db import Database, Message, MessageReaction
from _secrets import banned_user_ids

DB_PATH = os.path.join(os.path.dirname(__file__), '../bot.db')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Provide chat history JSON as an argument")
        sys.exit(1)

    json_path = sys.argv[1]
    db = Database(DB_PATH)

    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    banned_user_ids_str = {str(uid) for uid in banned_user_ids}

    msg_count = 0
    ignored_msg_count = 0
    reaction_count = 0
    reaction_count = 0

    for message in data['messages']:
        # Ignore reposts
        if not 'from_id' in message or not message['from_id'].startswith('user'):
            continue
        uid_str = message['from_id'][4:]
        # Ignore messages from banned users
        if uid_str in banned_user_ids_str:
            ignored_msg_count += 1
            continue
        # Ignore forwarded messages
        forwarded_from = message.get('forwarded_from', None)
        if forwarded_from is not None and forwarded_from != "null":
            continue

        text = "".join(t.get("text") for t in message.get('text_entities', []))
        if text != "" and not text.startswith("/"):
            m = Message(
                msg_id=int(message['id']),
                user_id=int(uid_str),
                ts=int(message['date_unixtime']) if 'date_unixtime' in message else 0,
                text=text
            )
            db.insert(m)
            msg_count += 1
            for reaction in message.get('reactions', []):
                rtype = reaction.get('type')
                if rtype == 'emoji':
                    emoji = reaction['emoji']
                elif rtype == 'custom_emoji':
                    doc_id = reaction.get('document_id', '')
                    if doc_id.isdigit():
                        emoji = doc_id
                    else:
                        print(f'Warning: Message {m.msg_id} has custom_emoji with non-integer document_id {doc_id}, run fill_reactions.py first')
                        continue
                else:
                    continue
                count = reaction['count']
                recent = reaction.get('recent', [])
                if len(recent) != count:
                    print(f'Warning: Message {m.msg_id} emoji {emoji} only has {len(recent)} out of {count} reactions, run fill_reactions.py first')
                for entry in recent:
                    from_id = entry.get('from_id', '')
                    if not from_id.startswith('user'):
                        continue
                    mr = MessageReaction(
                        msg_id=m.msg_id,
                        user_id=int(from_id[4:]),
                        emoji=emoji,
                        ts=int(datetime.fromisoformat(entry['date']).timestamp()) if 'date' in entry else 0
                    )
                    if mr.user_id in banned_user_ids:
                        continue
                    db.insert(mr)
                    reaction_count += 1

    db.commit()
    print(f'Imported {msg_count} messages and {reaction_count} reactions, ignored {ignored_msg_count} messages from banned users')
