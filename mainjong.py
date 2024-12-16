import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from game_logic import MahjongGame

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

bot_token = 'YOUR_BOT_TOKEN'

game = MahjongGame()

def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    update.message.reply_text("Welcome to the Mahjong game! Type /join to join the game.")

def join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    game.add_player(update.effective_user.id)
    update.message.reply_text("You've joined the game! Waiting for more players...")

def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if game.ready_to_start():
        game.start()
        update.message.reply_text("Game started! Check your private messages for your hand.")
    else:
        update.message.reply_text("Waiting for more players to join...")

def mainjong():
    application = ApplicationBuilder().token(bot_token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("join", join))
    application.add_handler(CommandHandler("startgame", start_game))

    application.run_polling()

if __name__ == '__main__':
    mainjong()
