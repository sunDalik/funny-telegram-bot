import sys
import os
import json
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", help = "Output JSON with identation", action="store_true")
    args = parser.parse_args()
 
    JSON_PATH = os.path.join(os.path.dirname(__file__), "../_secrets/messages.json") 
    old_size = os.path.getsize(JSON_PATH)

    with open(JSON_PATH, 'r+') as f:
        data = json.load(f)

        # Remove messages with no text
        messages = []
        old_messages_length = len(data['messages'])
        for message in data['messages']:
            forwarded_from = message.get("forwarded_from", None)
            if forwarded_from is not None and forwarded_from != "null":
                continue
            if "text_entities" in message and len(message.get("text_entities")) > 0:
                messages.append(message)
        new_messages_length = len(messages)
        
        print(f"messages.json contains {len(messages)} text messages")
        # Remove redudndant keys from messages
        for message in messages:
            message.pop("id", None)
            message.pop("type", None)
            message.pop("from", None)
            message.pop("date", None)
            message.pop("text", None)
            message.pop("edited", None)
            message.pop("edited_unixtime", None)
            message.pop("photo", None)
            message.pop("width", None)
            message.pop("height", None)
            message.pop("file", None)
            message.pop("thumbnail", None)
            message.pop("media_type", None)
            message.pop("reply_to_message_id", None)
            message.pop("sticker_emoji", None)
            message.pop("forwarded_from", None)
            message.pop("mime_type", None)
            message.pop("duration_seconds", None)
        data["messages"] = messages

        f.seek(0)
        indentation = 1 if args.debug else None
        json.dump(data, f, indent=indentation, ensure_ascii=False)
        f.truncate()

    new_size = os.path.getsize(JSON_PATH)
    print(f"Reduced file size from {old_size} to {new_size} bytes")
    print(f"Removed {old_messages_length - new_messages_length} forwarded or non-text messages")