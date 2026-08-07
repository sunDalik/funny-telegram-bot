from player_management import Player
from tile_management import Wall

class MahjongGame:
    def __init__(self):
        self.players = []
        self.wall = Wall()
        self.dora_indicators = []
        self.honbas = 0
        self.points = {}
        self.riichi_players = []
        self.round_wind = 'east'
        self.seat_winds = ['east', 'south', 'west', 'north']

    def add_player(self, player_id):
        if len(self.players) < 4:
            self.players.append(Player(player_id, self.seat_winds[len(self.players)]))
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

    def declare_riichi(self, player_id):
        self.riichi_players.append(player_id)
        for player in self.players:
            if player.user_id == player_id:
                player.notify_riichi()

    def check_win(self, player, tile=None):
        # Placeholder for actual win condition logic
        # This should check if the player has a valid Mahjong hand
        return False, []

    def calculate_score(self, player, winning_hand):
        base_points = 1000  # Placeholder for actual scoring
        dora_count = sum(tile in winning_hand for tile in self.dora_indicators)
        score = base_points * (2 ** dora_count)
        score += self.honbas * 300
        if player.user_id in self.riichi_players:
            score += 1000  # Bonus for winning after declaring riichi
        return score

    def end_round(self, winner_id, winning_hand):
        winner = next(player for player in self.players if player.user_id == winner_id)
        score = self.calculate_score(winner, winning_hand)
        for player in self.players:
            if player.user_id == winner_id:
                self.points[winner_id] += score
            else:
                self.points[player.user_id] -= score // 3
        self.honbas += 1
        self.broadcast_points()
        self.rotate_seat_winds()

    def rotate_seat_winds(self):
        if self.seat_winds[0] != 'east':
            self.round_wind = 'south'
        self.seat_winds = self.seat_winds[1:] + self.seat_winds[:1]
        for i, player in enumerate(self.players):
            player.seat_wind = self.seat_winds[i]

    def broadcast_points(self):
        for player in self.players:
            player.notify_points(self.points)
