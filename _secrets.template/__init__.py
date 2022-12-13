# If you don't have a bot token, talk to the @BotFather :)
# Don't forget to disable group privacy for the bot to work properly in group chats
secrets_bot_token = ""

# Whitelist of chats
# You can go to web.telegram.org to find your chat IDs
# Bot will also print them when you try to execute a blacklisted command
secrets_chat_ids = []

# "Banned" users
# Messages from these users will be ignored from messages.json and new messages won't be stored in DB
# It makes sense to put commonly used bots here in order to not dillute the message pool
banned_user_ids = []

# --- Custom replies ---
# Aliases for the Jerk of the Day that will randomly rotate daily
# Provide lowercase words in Nominative, Genitive, Genitive plural and Instrumental plural cases
jerk_aliases = [["придурок", "придурка", "придурков", "придурками"]]