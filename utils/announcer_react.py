import sys
import os
import asyncio
import re
from telegram import Bot, ReactionTypeEmoji

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _secrets import secrets_bot_token

EMOJIS = ["👍", "👎", "❤", "🔥", "🥰", "👏", "😁", "🤔", "🤯", "😱", "🤬", "😢", "🎉", "🤩", "🤮", "💩", "🙏", "👌", "🕊", "🤡", "🥱", "🥴", "😍", "🐳", "❤‍🔥", "🌚", "🌭", "💯", "🤣", "⚡", "🍌", "🏆", "💔", "🤨", "😐", "🍓",
          "🍾", "💋", "🖕", "😈", "😴", "😭", "🤓", "👻", "👨‍💻", "👀", "🎃", "🙈", "😇", "😨", "🤝", "✍", "🤗", "🫡", "🎅", "🎄", "☃", "💅", "🤪", "🗿", "🆒", "💘", "🙉", "🦄", "😘", "💊", "🙊", "😎", "👾", "🤷‍♂", "🤷", "🤷‍♀", "😡"]


async def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <https://t.me/c/CHATID/MSGID> '<emoji,emoji,...>'")
        print(f"Emojis: {' '.join(EMOJIS)}")
        sys.exit(0)

    m = re.match(r"https?://t\.me/c/(\d+)/(\d+)", sys.argv[1])
    if not m:
        print(f"Error: invalid link '{sys.argv[1]}', expected https://t.me/c/CHATID/MSGID")
        sys.exit(1)
    chat_id, message_id = int(f"-100{m.group(1)}"), int(m.group(2))

    emoji_str = sys.argv[2]
    reactions = [ReactionTypeEmoji(emoji=e) for e in emoji_str.split(",") if e]

    async with Bot(token=secrets_bot_token) as bot:
        await bot.set_message_reaction(chat_id=chat_id, message_id=message_id, reaction=reactions)


if __name__ == '__main__':
    asyncio.run(main())
