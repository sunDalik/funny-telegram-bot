import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _secrets import secrets_bot_token
from telegram.ext import Updater


if __name__ == '__main__':
    if (len(sys.argv) < 2):
         print("Provide chat ID as a command line argument")
         quit()
    u = Updater(secrets_bot_token, use_context=True)
    print(f"Enter a message that will be sent to chat {sys.argv[1]}. Press Ctrl+D to send.")
    
    message = sys.stdin.read()
    if (message != ""):
        u.bot.send_message(chat_id=sys.argv[1], text=message)