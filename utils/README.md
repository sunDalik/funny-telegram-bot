Bot utility scripts

### announcer.py chatid
Sends a custom message to the chat with id <chatid>

### announcer_react.py <https://t.me/c/CHATID/MSGID> <emoji,emoji,...>
Reacts to the linked message with the emoji(s); given an empty emoji string, removes own reactions from the message

### init_db.py
Creates a new SQLite database

### import_messages.py `<json>`
Reads the Telegram chat export `<json>` into the SQLite database

### import_sublime_sets.py `<json>`
Imports all the /set commands from the Telegram chat export `<json>` into the Redis database
