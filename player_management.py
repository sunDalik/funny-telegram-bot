from telegram import Bot

bot = Bot(token='YOUR_BOT_TOKEN')

class Player:
    def __init__(self, user_id, seat_wind):
        self.user_id = user_id
        self.hand = []
        self.seat_wind = seat_wind

    def draw_initial_hand(self, wall):
        self.hand = wall.draw_tiles(13)

    def notify_hand(self):
        hand_str = ''.join(self.hand)
        bot.send_message(self.user_id, f"Your hand: {hand_str} (Wind: {self.seat_wind})")

    def notify_discard(self, tile):
        bot.send_message(self.user_id, f"Player discarded: {tile}")

    def notify_new_dora(self, new_dora):
        bot.send_message(self.user_id, f"New Dora indicator revealed: {new_dora}")

    def notify_points(self, points):
        bot.send_message(self.user_id, f"Current points: {points[self.user_id]}")

    def notify_riichi(self):
        bot.send_message(self.user_id, "You have declared Riichi!")
