from player_management import Player
from tile_management import Wall

class MahjongGame:
    def __init__(self):
        self.players = []
        self.wall = Wall()
        self.dora_indicators = []
        self.honbas = 0
        self.points = {}

    def add_player(self, player_id):
        if len(self.players) < 4:
            self.players.append(Player(player_id))
            self.points[player_id] = 25000  # Starting points for each player
    
    def ready_to_start(self):
        return len(self.players) == 4
    
    def start(self):
        self.wall.shuffle()
        self.dora_indicators = self.wall.draw_dora_indicators()
        for player in self.players:
            player.draw_initial_hand(self.wall)
            player.notify_hand()
    
    def broadcast_discard(self, tile):
        for player in self.players:
            player.notify_discard(tile)
    
    def handle_kan(self):
        self.wall.kan_called()
        new_dora = self.wall.reveal_new_dora()
        if new_dora:
            self.dora_indicators.append(new_dora)
            self.broadcast_new_dora(new_dora)
    
    def broadcast_new_dora(self, new_dora):
        for player in self.players:
            player.notify_new_dora(new_dora)
    
    def end_round(self, winner_id, points_won):
        for player in self.players:
            if player.user_id == winner_id:
                self.points[winner_id] += points_won
            else:
                self.points[player.user_id] -= points_won // 3
        self.honbas += 1
        self.broadcast_points()

    def broadcast_points(self):
        for player in self.players:
            player.notify_points(self.points)
