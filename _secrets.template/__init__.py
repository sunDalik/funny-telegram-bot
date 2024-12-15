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

# Custom user aliases that can be used to refer to other users by their nicknames instead of usernames
# Keys are user IDs, values are lists of aliases
# Assigning the same alias to multiple users will choose a user randomly every time
user_aliases = {
    12345: ["john", "johnny", "jack"]
}

# "Suspects" whose messages participate in the Taki game
# Keys are user IDs, values are tuples of names to show in the inline keyboard and the number of raffle tickets
# (The suspect for each game is drawn randomly from a pool of tickets, more tickets = higher probability of being chosen)
taki_suspects = {
    12345: ("john", 10)
}

# --- Custom replies ---
# Aliases for the Jerk of the Day that will randomly rotate daily
# Provide lowercase words in Nominative, Genitive, Genitive plural and Instrumental plural cases
jerk_aliases = [["придурок", "придурка", "придурков", "придурками"]]