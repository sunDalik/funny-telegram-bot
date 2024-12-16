from player_management import Player
from tile_management import Wall

class MahjongGame:
    def __init__(self):
        self.players = []
        self.wall = Wall()
        self.dora_indicators = []
    
    def add_player(self, player_id):
        if len(self.players) < 4:
            self.players.append(Player(player_id))
    
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
