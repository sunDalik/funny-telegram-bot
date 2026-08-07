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

def declare_riichi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    player_id = update.effective_user.id
    game.declare_riichi(player_id)
    update.message.reply_text("You have declared Riichi!")

def win(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    player_id = update.effective_user.id
    player = next(player for player in game.players if player.user_id == player_id)
    is_win, winning_hand = game.check_win(player)
    if is_win:
        game.end_round(player_id, winning_hand)
        update.message.reply_text("Congratulations! You've won the round!")
    else:
        update.message.reply_text("Your hand is not a winning hand yet.")

# Add these handlers to your main function
def mainjong():
    application = ApplicationBuilder().token(bot_token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("join", join))
    application.add_handler(CommandHandler("startgame", start_game))
    application.add_handler(CommandHandler("riichi", declare_riichi))
    application.add_handler(CommandHandler("win", win))

    application.run_polling()

if __name__ == '__main__':
    mainjong()

