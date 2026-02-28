Bot utility scripts  

### announcer.py chatid
Sends a custom message to the chat with id <chatid>

### announcer_react.py <https://t.me/c/CHATID/MSGID> <emoji,emoji,...>
Reacts to the linked message with the emoji(s); given an empty emoji string, removes own reactions from the message

### strip_messages_json.py
Strips _secrets/messages.json from redundant data to reduce file size

### import_sublime_sets.py
Imports all the /set commands from _secrets/messages.json into its own redis database